"""
Portfolio Sync Service - FIXED VERSION

Synchronizes portfolio and positions from broker to database.

FIXES:
1. Properly finds existing portfolio by (broker, account_id)
2. Uses same session throughout to avoid detached object issues
3. Better error handling and logging
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from trading_cotrader.core.database.session import Session
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.repositories.position import PositionRepository
import trading_cotrader.core.models.domain as dm
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import PortfolioORM
logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of portfolio sync operation"""
    success: bool = False
    portfolio_id: str = ""
    positions_synced: int = 0
    positions_failed: int = 0
    error: str = ""
    warnings: List[str] = field(default_factory=list)


class PortfolioSyncService:
    """
    Synchronize portfolio from broker to database.
    
    IMPORTANT: This service must be used within a session_scope context.
    
    Usage:
        with session_scope() as session:
            sync_service = PortfolioSyncService(session, broker_adapter)
            result = sync_service.sync_portfolio()
            
            if result.success:
                print(f"Synced {result.positions_synced} positions")
    """
    
    def __init__(self, session: Session, broker):
        """
        Args:
            session: SQLAlchemy session (from session_scope)
            broker: Broker adapter (e.g., TastytradeAdapter)
        """
        self.session = session
        self.broker = broker
        self.portfolio_repo = PortfolioRepository(session)
        self.position_repo = PositionRepository(session)
    
    def sync_portfolio(self) -> SyncResult:
        """
        Main sync method - syncs portfolio and positions from broker.
        
        Returns:
            SyncResult with status and statistics
        """
        result = SyncResult()
        
        try:
            # Step 1: Get account info from broker
            logger.info("Fetching account balance from broker...")
            balance = self.broker.get_account_balance()
            
            if not balance:
                result.error = "Failed to get account balance"
                return result
            
            # Step 2: Get or create portfolio
            logger.info(f"Looking for portfolio: broker=tastytrade, account={self.broker.account_id}")
            portfolio = self._get_or_create_portfolio(balance)
            
            if not portfolio:
                result.error = "Failed to get/create portfolio"
                return result
            
            result.portfolio_id = portfolio.id
            logger.info(f"Using portfolio: {portfolio.id} ({portfolio.name})")
            
            # Step 3: Get positions from broker
            logger.info("Fetching positions from broker...")
            broker_positions = self.broker.get_positions()
            logger.info(f"Broker returned {len(broker_positions)} positions")
            
            # Step 4: Sync positions (clear and rebuild)
            sync_stats = self._sync_positions(portfolio.id, broker_positions)
            result.positions_synced = sync_stats['created']
            result.positions_failed = sync_stats['failed']
            result.warnings = sync_stats.get('warnings', [])
            
            # Step 5: Update portfolio Greeks and totals
            self._update_portfolio_aggregates(portfolio)
            
            # Commit everything
            self.session.commit()
            
            result.success = True
            logger.info(f"✓ Portfolio sync complete: {result.positions_synced} positions")
            
        except Exception as e:
            self.session.rollback()
            result.error = str(e)
            logger.error(f"Portfolio sync failed: {e}")
            logger.exception("Full error:")
        
        return result
    
    def _get_or_create_portfolio(self, balance: dict) -> Optional[dm.Portfolio]:
        """
        Get existing portfolio or create new one.
        
        CRITICAL: Uses get_by_account to find existing portfolio first!
        """
        broker_name = "tastytrade"
        account_id = self.broker.account_id
        
        # Try to find existing portfolio
        logger.debug(f"Querying for existing portfolio: broker={broker_name}, account={account_id}")
        existing = self.portfolio_repo.get_by_account(broker_name, account_id)
        
        if existing:
            logger.info(f"Found existing portfolio: {existing.id}")
            
            # Update with latest balance
            existing.cash_balance = balance.get('cash_balance', Decimal('0'))
            existing.buying_power = balance.get('buying_power', Decimal('0'))
            existing.total_equity = balance.get('net_liquidating_value', Decimal('0'))
            existing.last_updated = datetime.utcnow()
            
            # Save updates
            updated = self.portfolio_repo.update_from_domain(existing)
            return updated
        
        # Create new portfolio
        logger.info(f"Creating new portfolio for account {account_id}")
        
        new_portfolio = dm.Portfolio(
            name=f"Tastytrade {account_id}",
            broker=broker_name,
            account_id=account_id,
            cash_balance=balance.get('cash_balance', Decimal('0')),
            buying_power=balance.get('buying_power', Decimal('0')),
            total_equity=balance.get('net_liquidating_value', Decimal('0')),
        )
        
        created = self.portfolio_repo.create_from_domain(new_portfolio)
        
        if created:
            logger.info(f"Created new portfolio: {created.id}")
        else:
            logger.error("Failed to create portfolio")
        
        return created
    
    def _sync_positions(self, portfolio_id: str, broker_positions: List[dm.Position]) -> dict:
        """
        Sync positions using clear-and-rebuild strategy.
        
        Returns:
            dict with 'created', 'failed', 'warnings' keys
        """
        stats = {'created': 0, 'failed': 0, 'warnings': []}
        
        # Validate positions
        valid_positions = []
        for pos in broker_positions:
            is_valid, errors = self._validate_position(pos)
            if is_valid:
                valid_positions.append(pos)
            else:
                stats['warnings'].append(f"{pos.symbol.ticker}: {errors}")
        
        logger.info(f"Valid positions: {len(valid_positions)}, Invalid: {len(broker_positions) - len(valid_positions)}")
        
        # Clear existing positions
        deleted = self.position_repo.delete_by_portfolio(portfolio_id)
        logger.info(f"Deleted {deleted} existing positions")
        
        # Create new positions
        for pos in valid_positions:
            try:
                created = self.position_repo.create_from_domain(pos, portfolio_id)
                if created:
                    stats['created'] += 1
                else:
                    stats['failed'] += 1
                    logger.error(f"Failed to create position: {pos.symbol.ticker}")
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Error creating position {pos.symbol.ticker}: {e}")
        
        return stats
    
    def _validate_position(self, position: dm.Position) -> tuple:
        """Validate a position from broker"""
        errors = []
        
        if position.quantity == 0:
            errors.append("Zero quantity")
        
        if not position.symbol:
            errors.append("Missing symbol")
        
        # For options, check Greeks
        if position.symbol and position.symbol.asset_type == dm.AssetType.OPTION:
            if not position.greeks or (position.greeks.delta == 0 and position.greeks.gamma == 0):
                errors.append("Option has zero Greeks - likely not fetched from broker")
        
        if not position.broker_position_id:
            errors.append("Missing broker_position_id")
        
        return (len(errors) == 0, errors)
    
    def _update_portfolio_aggregates(self, portfolio: dm.Portfolio):
        """Update portfolio-level Greeks and totals"""
        
        # Get all positions for this portfolio
        positions = self.position_repo.get_by_portfolio(portfolio.id)
        
        # Calculate aggregates
        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')
        total_pnl = Decimal('0')
        total_value = Decimal('0')
        
        for pos in positions:
            if pos.greeks:
                total_delta += pos.greeks.delta or Decimal('0')
                total_gamma += pos.greeks.gamma or Decimal('0')
                total_theta += pos.greeks.theta or Decimal('0')
                total_vega += pos.greeks.vega or Decimal('0')
            
            total_pnl += pos.unrealized_pnl()
            total_value += pos.market_value or Decimal('0')
        
        # Update portfolio
        portfolio.portfolio_greeks = dm.Greeks(
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega
        )
        portfolio.total_pnl = total_pnl
        
        # Save
        self.portfolio_repo.update_from_domain(portfolio)
        
        logger.info(f"Portfolio aggregates: Δ={total_delta:.2f}, Θ={total_theta:.2f}, P&L=${total_pnl:.2f}")


# =============================================================================
# Diagnostic Function
# =============================================================================

def diagnose_portfolio_issue():
    """
    Run this to diagnose portfolio creation issues.
    
    Usage:
        from services.portfolio_sync import diagnose_portfolio_issue
        diagnose_portfolio_issue()
    """

    
    print("\n" + "=" * 60)
    print("PORTFOLIO DIAGNOSTIC")
    print("=" * 60)
    
    with session_scope() as session:
        # Count portfolios
        portfolios = session.query(PortfolioORM).all()
        print(f"\nTotal portfolios in DB: {len(portfolios)}")
        
        # Group by (broker, account_id)
        groups = {}
        for p in portfolios:
            key = (p.broker, p.account_id)
            if key not in groups:
                groups[key] = []
            groups[key].append(p)
        
        print(f"Unique (broker, account) combinations: {len(groups)}")
        
        for key, group in groups.items():
            print(f"\n  {key}:")
            for p in group:
                print(f"    ID: {p.id}")
                print(f"    Name: {p.name}")
                print(f"    Created: {p.created_at}")
            
            if len(group) > 1:
                print(f"    ⚠️  DUPLICATE DETECTED!")
        
        # Test the repository query
        print("\n" + "-" * 40)
        print("Testing PortfolioRepository.get_by_account():")
        
        repo = PortfolioRepository(session)
        for key in list(groups.keys())[:3]:  # Test first 3
            broker, account_id = key
            found = repo.get_by_account(broker, account_id)
            
            if found:
                print(f"  ✓ Found portfolio for {key}: {found.id}")
            else:
                print(f"  ❌ NOT FOUND for {key}!")
                print(f"     This is likely the bug - query returning None")


if __name__ == "__main__":
    diagnose_portfolio_issue()
