"""
Portfolio Sync Runner - Synchronize portfolio from Tastytrade

This is your main daily workflow command.
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings, setup_logging
from core.database.session import get_db_manager, session_scope
from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
from repositories.portfolio import PortfolioRepository
from repositories.position import PositionRepository
from repositories.trade import TradeRepository
from services.position_sync import PositionSyncService
import core.models.domain as dm
from services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class PortfolioSyncRunner:
    """Main runner for portfolio synchronization"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_db_manager()
        self.broker = None
        self.portfolio = None
    
    async def run(self):
        """Main sync workflow"""
        
        print("\n" + "=" * 80)
        print("PORTFOLIO SYNC - Tastytrade → Database")
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
        
        # Step 5: Update portfolio Greeks
        if not await self._update_portfolio_greeks():
            return False
        
        # Step 6: Capture daily snapshot (NEW!)
        await self._capture_snapshot()
        
        # Step 7: Display summary
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
                
                # Try to find existing
                self.portfolio = portfolio_repo.get_by_account(
                    broker="tastytrade",
                    account_id=self.broker.account_id
                )
                
                if self.portfolio:
                    print(f"✓ Found existing portfolio: {self.portfolio.name}")
                else:
                    # Create new
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
            
            # Update portfolio
            self.portfolio.cash_balance = balance['cash_balance']
            self.portfolio.buying_power = balance['buying_power']
            self.portfolio.total_equity = balance.get('net_liquidating_value', balance['cash_balance'])
            
            # Save to database
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
            
            if not broker_positions:
                print("⚠️  No positions found at broker")
                # Still need to clear DB positions
            
            print(f"✓ Fetched {len(broker_positions)} positions from Tastytrade")
            
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
            
            if not result['success']:
                print("⚠️  Position count mismatch detected")
            
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
                position_repo = PositionRepository(session)
                portfolio_repo = PortfolioRepository(session)
                
                # Get all positions
                positions = position_repo.get_by_portfolio(self.portfolio.id)
                
                # Calculate Greeks
                total_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
                total_gamma = sum(p.greeks.gamma if p.greeks else 0 for p in positions)
                total_theta = sum(p.greeks.theta if p.greeks else 0 for p in positions)
                total_vega = sum(p.greeks.vega if p.greeks else 0 for p in positions)
                
                # Update portfolio
                self.portfolio.portfolio_greeks = dm.Greeks(
                    delta=total_delta,
                    gamma=total_gamma,
                    theta=total_theta,
                    vega=total_vega
                )
                
                # Calculate P&L
                self.portfolio.total_pnl = sum(p.unrealized_pnl() for p in positions)
                
                # Save
                portfolio_repo.update_from_domain(self.portfolio)
            
            print(f"✓ Portfolio Delta: {total_delta:.2f}")
            print(f"✓ Portfolio Theta: {total_theta:.2f}")
            print(f"✓ Portfolio Vega:  {total_vega:.2f}")
            
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
            position_repo = PositionRepository(session)
            positions = position_repo.get_by_portfolio(self.portfolio.id)
            
            # Group by underlying
            by_underlying = {}
            for pos in positions:
                underlying = pos.symbol.ticker
                if underlying not in by_underlying:
                    by_underlying[underlying] = []
                by_underlying[underlying].append(pos)
            
            print(f"\nPortfolio: {self.portfolio.name}")
            print(f"Total Positions: {len(positions)}")
            print(f"Unique Underlyings: {len(by_underlying)}")
            print(f"Total P&L: ${self.portfolio.total_pnl:,.2f}")
            print(f"\nGreeks:")
            print(f"  Δ = {self.portfolio.portfolio_greeks.delta:.2f}")
            print(f"  Γ = {self.portfolio.portfolio_greeks.gamma:.4f}")
            print(f"  Θ = {self.portfolio.portfolio_greeks.theta:.2f}")
            print(f"  V = {self.portfolio.portfolio_greeks.vega:.2f}")

    async def _capture_snapshot(self) -> bool:
        """Capture daily snapshot for analytics"""
        print("\n📸 Capturing daily snapshot...")
        
        try:
            with session_scope() as session:
                position_repo = PositionRepository(session)
                trade_repo = TradeRepository(session)
                
                # Get current positions and trades
                positions = position_repo.get_by_portfolio(self.portfolio.id)
                trades = trade_repo.get_by_portfolio(self.portfolio.id, open_only=True)
                
                # Capture snapshot
                snapshot_service = SnapshotService(session)
                success = snapshot_service.capture_daily_snapshot(
                    self.portfolio,
                    positions,
                    trades
                )
                
                if success:
                    print("✓ Daily snapshot captured")
                    
                    # Show quick stats
                    stats = snapshot_service.get_summary_stats(self.portfolio.id, days=7)
                    if stats and stats['days_tracked'] > 1:
                        print(f"\n📊 Last 7 days:")
                        print(f"  Days tracked: {stats['days_tracked']}")
                        print(f"  Total P&L: ${stats['total_pnl']:,.2f}")
                        print(f"  Win rate: {stats.get('win_rate', 0):.1f}%")
                    
                    return True
                else:
                    print("⚠️  Snapshot failed")
                    return False
            
        except Exception as e:
            print(f"❌ Snapshot capture failed: {e}")
            logger.exception("Full error:")
            return False

async def main():
    """Main entry point"""
    
    # Setup
    setup_logging()
    
    try:
        runner = PortfolioSyncRunner()
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