"""
Portfolio Sync with Greeks - WORKING VERSION

This version:
1. Syncs all positions (with or without Greeks)
2. Logs which positions need Greeks
3. Provides next steps for Greeks calculation

Run this to get your positions into the database NOW.
Calculate Greeks in next step (separate script).
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
import core.models.domain as dm

logger = logging.getLogger(__name__)


class PortfolioSyncWithGreeks:
    """Portfolio sync - Greeks calculated separately"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_db_manager()
        self.broker = None
        self.portfolio = None
    
    async def run(self):
        """Main sync workflow"""
        
        print("\n" + "=" * 80)
        print("PORTFOLIO SYNC")
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
        
        # Step 4: Sync positions
        if not await self._sync_positions():
            return False
        
        # Step 5: Update portfolio Greeks (from existing position Greeks)
        if not await self._update_portfolio_greeks():
            return False
        
        # Step 6: Display summary
        self._display_summary()
        
        print("\n✅ Portfolio sync complete!")
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
    
    async def _sync_positions(self) -> bool:
        """Sync positions from broker"""
        print("\n📊 Syncing positions...")
        
        try:
            # Fetch from broker
            broker_positions = await asyncio.to_thread(self.broker.get_positions)
            
            print(f"✓ Fetched {len(broker_positions)} positions from Tastytrade")
            
            # Analyze positions
            option_positions = []
            equity_positions = []
            positions_with_greeks = []
            positions_without_greeks = []
            
            for pos in broker_positions:
                if pos.symbol.asset_type == dm.AssetType.OPTION:
                    option_positions.append(pos)
                    if pos.greeks and pos.greeks.delta != 0:
                        positions_with_greeks.append(pos)
                    else:
                        positions_without_greeks.append(pos)
                elif pos.symbol.asset_type == dm.AssetType.EQUITY:
                    equity_positions.append(pos)
                    # Ensure equity has Greeks (delta = quantity)
                    if not pos.greeks or pos.greeks.delta == 0:
                        pos.greeks = dm.Greeks(
                            delta=Decimal(str(pos.quantity)),
                            timestamp=datetime.utcnow()
                        )
                    positions_with_greeks.append(pos)
            
            print(f"  Options: {len(option_positions)}")
            print(f"  Equities: {len(equity_positions)}")
            print(f"  With Greeks: {len(positions_with_greeks)}")
            print(f"  Without Greeks: {len(positions_without_greeks)}")
            
            # Sync to database
            with session_scope() as session:
                sync_service = PositionSyncService(session)
                result = sync_service.sync_positions(self.portfolio.id, broker_positions)
            
            # Display results
            print(f"\nSync Results:")
            print(f"  Deleted:  {result['deleted']}")
            print(f"  Created:  {result['created']}")
            print(f"  Failed:   {result['failed']}")
            print(f"  Invalid:  {result['invalid']}")
            print(f"  Final:    {result['final_count']}")
            
            # Greeks status
            if len(positions_without_greeks) > 0:
                print(f"\n⚠️  {len(positions_without_greeks)} option positions without Greeks:")
                for pos in positions_without_greeks[:5]:  # Show first 5
                    print(f"     - {pos.symbol.ticker}")
                if len(positions_without_greeks) > 5:
                    print(f"     ... and {len(positions_without_greeks) - 5} more")
                
                print(f"\n💡 Next Step: Calculate Greeks")
                print(f"   Greeks calculation requires:")
                print(f"   1. Market hours (for live quotes)")
                print(f"   2. Or historical data")
                print(f"   3. Run: python analytics/calculate_greeks.py")
            
            return True
            
        except Exception as e:
            print(f"❌ Position sync failed: {e}")
            logger.exception("Full error:")
            return False
    
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
                positions_with_greeks = [p for p in positions if p.greeks and p.greeks.delta != 0]
                
                if positions_with_greeks:
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
                    
                    print(f"✓ Portfolio Delta: {total_delta:.2f}")
                    print(f"✓ Portfolio Theta: {total_theta:.2f}")
                    print(f"✓ Portfolio Vega:  {total_vega:.2f}")
                    print(f"✓ Coverage: {len(positions_with_greeks)}/{len(positions)} positions")
                else:
                    print("⚠️  No positions with Greeks yet")
                    self.portfolio.portfolio_greeks = dm.Greeks(
                        delta=Decimal('0'),
                        gamma=Decimal('0'),
                        theta=Decimal('0'),
                        vega=Decimal('0')
                    )
                
                # Calculate P&L
                self.portfolio.total_pnl = sum(p.unrealized_pnl() for p in positions)
                
                portfolio_repo.update_from_domain(self.portfolio)
            
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
            
            positions_with_greeks = [p for p in positions if p.greeks and p.greeks.delta != 0]
            positions_without_greeks = [p for p in positions if not p.greeks or p.greeks.delta == 0]
            
            print(f"\nPortfolio: {self.portfolio.name}")
            print(f"Total Positions: {len(positions)}")
            print(f"  With Greeks: {len(positions_with_greeks)}")
            print(f"  Without Greeks: {len(positions_without_greeks)}")
            
            if positions_without_greeks:
                print(f"\n⚠️  Positions needing Greeks calculation:")
                for p in positions_without_greeks:
                    print(f"    - {p.symbol.ticker} ({p.symbol.asset_type.value})")
            
            print(f"\nTotal P&L: ${self.portfolio.total_pnl:,.2f}")
            
            if self.portfolio.portfolio_greeks:
                print(f"\nPortfolio Greeks (from {len(positions_with_greeks)} positions):")
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