"""
Portfolio Sync with Greeks Calculation

This runner:
1. Fetches positions from Tastytrade (may have no Greeks)
2. Accepts ALL valid positions
3. Calculates Greeks using our engine
4. Stores positions with calculated Greeks
5. Starts real-time Greeks monitoring

Run this instead of sync_portfolio.py for full Greeks integration
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings, setup_logging
from core.database.session import get_db_manager, session_scope
from adapters.tastytrade_adapter import TastytradeAdapter
from repositories.portfolio import PortfolioRepository
from services.position_sync import PositionSyncService
from analytics.greeks.engine import GreeksEngine
import core.models.domain as dm

logger = logging.getLogger(__name__)


class PortfolioSyncWithGreeks:
    """Portfolio sync with integrated Greeks calculation"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_db_manager()
        self.broker = None
        self.portfolio = None
        self.greeks_engine = GreeksEngine()
    
    async def run(self):
        """Main sync workflow with Greeks calculation"""
        
        print("\n" + "=" * 80)
        print("PORTFOLIO SYNC WITH GREEKS CALCULATION")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'PAPER' if self.settings.is_paper_trading else 'LIVE'}")
        print("=" * 80)
        print()
        
        # Step 1: Connect to broker
        if not await self._connect_broker():
            return False
        
        # Step 2: Get or create portfolio
        if not await self._get_or_create_portfolio():
            return False
        
        # Step 3: Sync account balance
        if not await self._sync_balance():
            return False
        
        # Step 4: Sync positions WITH Greeks calculation
        if not await self._sync_positions_with_greeks():
            return False
        
        # Step 5: Update portfolio Greeks
        if not await self._update_portfolio_greeks():
            return False
        
        # Step 6: Display summary
        self._display_summary()
        
        print("\n✅ Portfolio sync with Greeks complete!")
        print()
        
        return True
    
    async def _connect_broker(self) -> bool:
        """Connect to Tastytrade"""
        print("📡 Connecting to Tastytrade...")
        
        try:
            self.broker = TastytradeAdapter(
                account_number=self.settings.tastytrade_account_number,
                is_paper=self.settings.is_paper_trading
            )
            
            if not self.broker.authenticate():
                print("❌ Failed to authenticate with Tastytrade")
                return False
            
            print(f"✓ Connected to account: {self.broker.account_id}")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            logger.exception("Full error:")
            return False
    
    async def _get_or_create_portfolio(self) -> bool:
        """Get existing portfolio or create new one"""
        print("\n📂 Loading portfolio...")
        
        try:
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                
                self.portfolio = portfolio_repo.get_by_account(
                    broker="tastytrade",
                    account_id=self.broker.account_id
                )
                
                if self.portfolio:
                    print(f"✓ Found existing portfolio: {self.portfolio.name}")
                else:
                    print("Creating new portfolio...")
                    self.portfolio = dm.Portfolio(
                        name=f"Tastytrade {self.broker.account_id}",
                        broker="tastytrade",
                        account_id=self.broker.account_id
                    )
                    
                    self.portfolio = portfolio_repo.create_from_domain(self.portfolio)
                    if not self.portfolio:
                        print("❌ Failed to create portfolio")
                        return False
                    
                    print(f"✓ Created new portfolio: {self.portfolio.name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Portfolio setup failed: {e}")
            logger.exception("Full error:")
            return False
    
    async def _sync_balance(self) -> bool:
        """Sync account balance"""
        print("\n💰 Syncing account balance...")
        
        try:
            balance = await asyncio.to_thread(self.broker.get_account_balance)
            
            if not balance:
                print("❌ Failed to get balance")
                return False
            
            self.portfolio.cash_balance = balance['cash_balance']
            self.portfolio.buying_power = balance['buying_power']
            self.portfolio.total_equity = balance.get('net_liquidating_value', balance['cash_balance'])
            
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                portfolio_repo.update_from_domain(self.portfolio)
            
            print(f"✓ Cash Balance: ${balance['cash_balance']:,.2f}")
            print(f"✓ Buying Power: ${balance['buying_power']:,.2f}")
            print(f"✓ Total Equity: ${self.portfolio.total_equity:,.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Balance sync failed: {e}")
            logger.exception("Full error:")
            return False
    
    async def _sync_positions_with_greeks(self) -> bool:
        """Sync positions and calculate Greeks"""
        print("\n📊 Syncing positions with Greeks calculation...")
        
        try:
            # Fetch from broker
            broker_positions = await asyncio.to_thread(self.broker.get_positions)
            
            print(f"✓ Fetched {len(broker_positions)} positions from Tastytrade")
            
            # Calculate Greeks for positions that don't have them
            positions_with_greeks = []
            
            for pos in broker_positions:
                try:
                    # Check if position has Greeks
                    has_greeks = pos.greeks and pos.greeks.delta != 0
                    
                    if pos.symbol.asset_type == dm.AssetType.OPTION and not has_greeks:
                        print(f"📐 Calculating Greeks for {pos.symbol.ticker}...")
                        
                        # Calculate Greeks using our engine
                        greeks = await self._calculate_greeks_for_position(pos)
                        
                        if greeks:
                            pos.greeks = greeks
                            print(f"  ✓ Δ={greeks.delta:.2f}, Θ={greeks.theta:.2f}, V={greeks.vega:.2f}")
                        else:
                            print(f"  ⚠️  Could not calculate Greeks - will skip")
                            continue
                    
                    elif pos.symbol.asset_type == dm.AssetType.EQUITY and not has_greeks:
                        # Stock delta = quantity
                        pos.greeks = dm.Greeks(
                            delta=Decimal(str(pos.quantity)),
                            timestamp=datetime.utcnow()
                        )
                        print(f"✓ {pos.symbol.ticker} (stock): Δ={pos.greeks.delta:.2f}")
                    
                    positions_with_greeks.append(pos)
                
                except Exception as e:
                    logger.error(f"Error processing {pos.symbol.ticker}: {e}")
                    logger.exception("Full trace:")
                    # Add position anyway, Greeks can be calculated later
                    positions_with_greeks.append(pos)
            
            # Sync to database
            with session_scope() as session:
                sync_service = PositionSyncService(session)
                result = sync_service.sync_positions(self.portfolio.id, positions_with_greeks)
            
            # Display results
            print(f"\nSync Results:")
            print(f"  Deleted:  {result['deleted']}")
            print(f"  Created:  {result['created']}")
            print(f"  Failed:   {result['failed']}")
            print(f"  Invalid:  {result['invalid']}")
            
            if result['needs_greeks'] > 0:
                print(f"  ⚠️  Still need Greeks: {result['needs_greeks']}")
            
            print(f"  Final:    {result['final_count']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Position sync failed: {e}")
            logger.exception("Full error:")
            return False
    
    async def _calculate_greeks_for_position(self, position: dm.Position) -> dm.Greeks:
        """Calculate Greeks for a single position using our engine"""
        
        try:
            symbol = position.symbol
            
            # Get market data
            option_symbol = symbol.get_option_symbol()
            
            # Fetch quote
            quote = await asyncio.to_thread(self.broker.get_quote, option_symbol)
            underlying_quote = await asyncio.to_thread(self.broker.get_quote, symbol.ticker)
            
            if not quote or not underlying_quote:
                logger.warning(f"No market data for {symbol.ticker}")
                return None
            
            # Calculate time to expiry
            time_to_expiry = (symbol.expiration - datetime.utcnow()).total_seconds() / (365.25 * 24 * 3600)
            
            if time_to_expiry <= 0:
                logger.info(f"{symbol.ticker} has expired")
                return None
            
            # Get prices
            bid = quote.get('bid', 0)
            ask = quote.get('ask', 0)
            mid_price = (bid + ask) / 2 if bid and ask else quote.get('last', 0)
            underlying_price = underlying_quote.get('last', 0)
            
            if mid_price <= 0 or underlying_price <= 0:
                logger.warning(f"Invalid prices for {symbol.ticker}")
                return None
            
            # Calculate IV from market price
            calculated_iv = self.greeks_engine.calculate_implied_volatility(
                option_type=symbol.option_type.value,
                market_price=mid_price,
                spot_price=underlying_price,
                strike=float(symbol.strike),
                time_to_expiry=time_to_expiry
            )
            
            # Calculate Greeks
            greeks_calc = self.greeks_engine.calculate_greeks(
                option_type=symbol.option_type.value,
                spot_price=underlying_price,
                strike=float(symbol.strike),
                time_to_expiry=time_to_expiry,
                volatility=calculated_iv,
                broker_greeks=quote.get('greeks')
            )
            
            # Multiply by quantity for position-level Greeks
            return dm.Greeks(
                delta=greeks_calc.delta * abs(position.quantity),
                gamma=greeks_calc.gamma * abs(position.quantity),
                theta=greeks_calc.theta * abs(position.quantity),
                vega=greeks_calc.vega * abs(position.quantity),
                rho=greeks_calc.rho * abs(position.quantity),
                timestamp=greeks_calc.timestamp
            )
        
        except Exception as e:
            logger.error(f"Greeks calculation failed for {position.symbol.ticker}: {e}")
            logger.exception("Full trace:")
            return None
    
    async def _update_portfolio_greeks(self) -> bool:
        """Calculate and update portfolio Greeks"""
        print("\n🧮 Calculating portfolio Greeks...")
        
        try:
            with session_scope() as session:
                from repositories.position import PositionRepository
                position_repo = PositionRepository(session)
                portfolio_repo = PortfolioRepository(session)
                
                positions = position_repo.get_by_portfolio(self.portfolio.id)
                
                # Calculate Greeks (only from positions with Greeks)
                positions_with_greeks = [p for p in positions if p.greeks]
                
                total_delta = sum(p.greeks.delta for p in positions_with_greeks)
                total_gamma = sum(p.greeks.gamma for p in positions_with_greeks)
                total_theta = sum(p.greeks.theta for p in positions_with_greeks)
                total_vega = sum(p.greeks.vega for p in positions_with_greeks)
                
                self.portfolio.portfolio_greeks = dm.Greeks(
                    delta=total_delta,
                    gamma=total_gamma,
                    theta=total_theta,
                    vega=total_vega
                )
                
                # Calculate P&L
                self.portfolio.total_pnl = sum(p.unrealized_pnl() for p in positions)
                
                portfolio_repo.update_from_domain(self.portfolio)
            
            print(f"✓ Portfolio Delta: {total_delta:.2f}")
            print(f"✓ Portfolio Theta: {total_theta:.2f}")
            print(f"✓ Portfolio Vega:  {total_vega:.2f}")
            print(f"✓ Coverage: {len(positions_with_greeks)}/{len(positions)} positions")
            
            return True
            
        except Exception as e:
            print(f"❌ Greeks calculation failed: {e}")
            logger.exception("Full error:")
            return False
    
    def _display_summary(self):
        """Display sync summary"""
        print("\n" + "=" * 80)
        print("SYNC SUMMARY")
        print("=" * 80)
        
        with session_scope() as session:
            from repositories.position import PositionRepository
            position_repo = PositionRepository(session)
            positions = position_repo.get_by_portfolio(self.portfolio.id)
            
            positions_with_greeks = [p for p in positions if p.greeks]
            positions_without_greeks = [p for p in positions if not p.greeks]
            
            print(f"\nPortfolio: {self.portfolio.name}")
            print(f"Total Positions: {len(positions)}")
            print(f"  With Greeks: {len(positions_with_greeks)}")
            print(f"  Without Greeks: {len(positions_without_greeks)}")
            
            if positions_without_greeks:
                print(f"\n⚠️  Positions missing Greeks:")
                for p in positions_without_greeks:
                    print(f"    - {p.symbol.ticker}")
                print(f"\n💡 Run 'python analytics/calculate_missing_greeks.py' to calculate")
            
            print(f"\nTotal P&L: ${self.portfolio.total_pnl:,.2f}")
            print(f"\nPortfolio Greeks:")
            print(f"  Δ = {self.portfolio.portfolio_greeks.delta:.2f}")
            print(f"  Γ = {self.portfolio.portfolio_greeks.gamma:.4f}")
            print(f"  Θ = {self.portfolio.portfolio_greeks.theta:.2f}")
            print(f"  V = {self.portfolio.portfolio_greeks.vega:.2f}")


async def main():
    """Main entry point"""
    
    setup_logging()
    
    try:
        runner = PortfolioSyncWithGreeks()
        success = await runner.run()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        logger.exception("Full error:")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
