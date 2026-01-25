"""
Portfolio Sync Service

Business logic for syncing portfolio from broker to database.
Can be called from CLI, web UI, scheduled jobs, etc.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from trading_cotrader.core.database.session import Session
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.repositories.position import PositionRepository
from trading_cotrader.services.position_sync import PositionSyncService
import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of portfolio sync operation"""
    success: bool
    portfolio_id: Optional[str] = None
    positions_synced: int = 0
    positions_failed: int = 0
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PortfolioSyncService:
    """
    Service for syncing portfolio from broker
    
    Handles:
    - Account balance sync
    - Position sync
    - Portfolio Greeks calculation
    """
    
    def __init__(self, session: Session, broker):
        """
        Initialize sync service
        
        Args:
            session: Database session
            broker: Broker adapter (e.g. TastytradeAdapter)
        """
        self.session = session
        self.broker = broker
        self.portfolio_repo = PortfolioRepository(session)
        self.position_repo = PositionRepository(session)
        self.position_sync = PositionSyncService(session)
    
    def sync_portfolio(self, account_id: Optional[str] = None) -> SyncResult:
        """
        Sync entire portfolio from broker
        
        Steps:
        1. Get or create portfolio
        2. Sync account balance
        3. Sync positions
        4. Calculate portfolio Greeks
        
        Args:
            account_id: Specific account (uses broker default if not provided)
            
        Returns:
            SyncResult with success/failure info
        """
        
        try:
            logger.info("Starting portfolio sync")
            
            # Step 1: Get or create portfolio
            portfolio = self._get_or_create_portfolio()
            if not portfolio:
                return SyncResult(
                    success=False,
                    error="Failed to get/create portfolio"
                )
            
            logger.info(f"Syncing portfolio: {portfolio.name}")
            
            # Step 2: Sync balance
            balance_success = self._sync_balance(portfolio.id)
            if not balance_success:
                return SyncResult(
                    success=False,
                    portfolio_id=portfolio.id,
                    error="Failed to sync balance"
                )
            
            # Step 3: Sync positions
            broker_positions = self.broker.get_positions()
            
            sync_result = self.position_sync.sync_positions(
                portfolio.id,
                broker_positions
            )
            
            # Step 4: Update portfolio Greeks
            greeks_success = self._update_portfolio_greeks(portfolio.id)
            
            logger.info(f"✓ Portfolio sync complete")
            
            return SyncResult(
                success=sync_result['success'],
                portfolio_id=portfolio.id,
                positions_synced=sync_result['created'],
                positions_failed=sync_result['failed'],
                details=sync_result
            )
            
        except Exception as e:
            logger.error(f"Portfolio sync failed: {e}", exc_info=True)
            return SyncResult(
                success=False,
                error=str(e)
            )
    
    def _get_or_create_portfolio(self) -> Optional[dm.Portfolio]:
        """Get existing portfolio or create new one"""
        try:
            # Try to find existing
            portfolio = self.portfolio_repo.get_by_account(
                broker="tastytrade",
                account_id=self.broker.account_id
            )
            
            if portfolio:
                logger.info(f"Found existing portfolio: {portfolio.name}")
                return portfolio
            
            # Create new
            logger.info("Creating new portfolio")
            portfolio = dm.Portfolio(
                name=f"Tastytrade {self.broker.account_id}",
                broker="tastytrade",
                account_id=self.broker.account_id
            )
            
            created = self.portfolio_repo.create_from_domain(portfolio)
            if created:
                logger.info(f"Created portfolio: {created.name}")
            return created
            
        except Exception as e:
            logger.error(f"Error getting/creating portfolio: {e}")
            return None
    
    def _sync_balance(self, portfolio_id: str) -> bool:
        """Sync account balance"""
        try:
            logger.info("Syncing account balance")
            
            balance = self.broker.get_account_balance()
            if not balance:
                logger.error("Failed to get balance from broker")
                return False
            
            # Get the current portfolio
            portfolio = self.portfolio_repo.get_by_id(portfolio_id)
            if not portfolio:
                logger.error(f"Portfolio {portfolio_id} not found")
                return False
            
            # Update domain model
            portfolio.cash_balance = balance['cash_balance']
            portfolio.buying_power = balance['buying_power']
            portfolio.total_equity = balance.get('net_liquidating_value', balance['cash_balance'])
            
            # Save back to database
            updated = self.portfolio_repo.update_from_domain(portfolio)
            
            if updated:
                logger.info(f"✓ Balance synced: ${balance['cash_balance']:,.2f}")
                return True
            else:
                logger.error("Failed to update portfolio balance")
                return False
            
        except Exception as e:
            logger.error(f"Balance sync failed: {e}", exc_info=True)
            return False
    
    def _update_portfolio_greeks(self, portfolio_id: str) -> bool:
        """Calculate and update portfolio Greeks"""
        try:
            logger.info("Calculating portfolio Greeks")
            
            # Get portfolio
            portfolio = self.portfolio_repo.get_by_id(portfolio_id)
            if not portfolio:
                logger.error(f"Portfolio {portfolio_id} not found")
                return False
            
            # Get all positions
            positions = self.position_repo.get_by_portfolio(portfolio_id)
            
            # Calculate Greeks
            total_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
            total_gamma = sum(p.greeks.gamma if p.greeks else 0 for p in positions)
            total_theta = sum(p.greeks.theta if p.greeks else 0 for p in positions)
            total_vega = sum(p.greeks.vega if p.greeks else 0 for p in positions)
            
            # Update portfolio
            portfolio.portfolio_greeks = dm.Greeks(
                delta=total_delta,
                gamma=total_gamma,
                theta=total_theta,
                vega=total_vega
            )
            
            # Calculate P&L
            portfolio.total_pnl = sum(p.unrealized_pnl() for p in positions)
            
            # Save
            updated = self.portfolio_repo.update_from_domain(portfolio)
            
            if updated:
                logger.info(f"✓ Greeks updated: Δ={total_delta:.2f}, Θ={total_theta:.2f}")
                return True
            else:
                logger.error("Failed to update portfolio Greeks")
                return False
            
        except Exception as e:
            logger.error(f"Greeks calculation failed: {e}", exc_info=True)
            return False


# ============================================================================
# Testing
# ============================================================================

def main():
    """
    Test portfolio sync service
    
    Usage:
        python -m services.portfolio_sync
    """
    from trading_cotrader.config.settings import setup_logging, get_settings
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
    
    # Setup
    setup_logging()
    settings = get_settings()
    
    print("=" * 80)
    print("PORTFOLIO SYNC SERVICE - Test")
    print("=" * 80)
    print()
    
    # Connect to broker
    print("Connecting to broker...")
    try:
        broker = TastytradeAdapter(
            account_number=settings.tastytrade_account_number,
            is_paper=settings.is_paper_trading
        )
        
        if not broker.authenticate():
            print("✗ Failed to authenticate")
            return 1
        
        print(f"✓ Connected to account: {broker.account_id}")
        print()
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        logger.exception("Full error:")
        return 1
    
    # Run sync
    print("Running portfolio sync...")
    print("-" * 80)
    
    with session_scope() as session:
        sync_service = PortfolioSyncService(session, broker)
        result = sync_service.sync_portfolio()
        
        if result.success:
            print(f"\n✓ Sync completed successfully!")
            print(f"  Portfolio ID: {result.portfolio_id}")
            print(f"  Positions synced: {result.positions_synced}")
            print(f"  Positions failed: {result.positions_failed}")
            
            if result.details:
                print(f"\n  Details:")
                print(f"    Deleted: {result.details.get('deleted', 0)}")
                print(f"    Created: {result.details.get('created', 0)}")
                print(f"    Invalid: {result.details.get('invalid', 0)}")
                print(f"    Final count: {result.details.get('final_count', 0)}")
        else:
            print(f"\n✗ Sync failed: {result.error}")
            return 1
    
    # Verify
    print("\n" + "-" * 80)
    print("Verifying sync...")
    
    with session_scope() as session:
        portfolio_repo = PortfolioRepository(session)
        position_repo = PositionRepository(session)
        
        portfolio = portfolio_repo.get_by_id(result.portfolio_id)
        if portfolio:
            print(f"\n✓ Portfolio: {portfolio.name}")
            print(f"  Cash: ${portfolio.cash_balance:,.2f}")
            print(f"  Buying Power: ${portfolio.buying_power:,.2f}")
            print(f"  Total Equity: ${portfolio.total_equity:,.2f}")
            
            if portfolio.portfolio_greeks:
                print(f"\n  Portfolio Greeks:")
                print(f"    Δ = {portfolio.portfolio_greeks.delta:.2f}")
                print(f"    Γ = {portfolio.portfolio_greeks.gamma:.4f}")
                print(f"    Θ = {portfolio.portfolio_greeks.theta:.2f}")
                print(f"    V = {portfolio.portfolio_greeks.vega:.2f}")
            
            positions = position_repo.get_by_portfolio(portfolio.id)
            print(f"\n  Positions: {len(positions)}")
            
            # Show first few positions
            for pos in positions[:3]:
                print(f"    - {pos.symbol.ticker}: {pos.quantity} @ ${pos.current_price}")
    
    print("\n" + "=" * 80)
    print("✓ Test completed")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
    
    ''' Delte these files
   runners/sync_portfolio.py
   runners/sync_with_greeks.py
   runners/sync_with_greeks_old.py
   services/real_risk_check.py  (or merge into risk_checker.py)
   services/risk_limits_test_script.py
    '''