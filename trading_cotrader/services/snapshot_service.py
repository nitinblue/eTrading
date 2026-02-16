"""
Snapshot Service - Capture portfolio state over time

This is the foundation for all analytics and ML:
- Daily portfolio snapshots
- Position Greeks history
- Enables time-series analysis and pattern detection
"""

from trading_cotrader.config.settings import setup_logging
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.repositories.position import PositionRepository

import logging
from typing import List, Dict
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.orm import Session
from trading_cotrader.core.database.schema import (
    DailyPerformanceORM,
    GreeksHistoryORM,
    PortfolioORM,
    PositionORM,
)
import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class SnapshotService:
    """
    Captures point-in-time snapshots of portfolio state
    
    This is the foundation for:
    - Time-series analytics (Greeks over time, P&L trends)
    - Pattern detection (when do you adjust, exit timing)
    - Risk alerts (delta breaches, concentration changes)
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def capture_daily_snapshot(
        self,
        portfolio: dm.Portfolio,
        positions: List[dm.Position],
        trades: List[dm.Trade] = None
    ) -> bool:
        """
        Capture complete portfolio state for today
        
        This creates:
        1. DailyPerformanceORM - Portfolio-level snapshot
        2. GreeksHistoryORM - Position-level Greeks snapshot
        
        Args:
            portfolio: Current portfolio state
            positions: All current positions
            trades: All current trades (optional, for trade count)
            
        Returns:
            True if snapshot captured successfully
        """
        try:
            snapshot_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            logger.info(f"Capturing daily snapshot for {snapshot_date.date()}")
            
            # Step 1: Capture portfolio-level snapshot
            portfolio_snapshot = self._create_portfolio_snapshot(
                portfolio, positions, trades, snapshot_date
            )
            
            if not portfolio_snapshot:
                logger.error("Failed to create portfolio snapshot")
                return False
            
            # Step 2: Capture position-level Greeks history
            greeks_captured = self._capture_greeks_history(positions, snapshot_date)
            
            # Step 3: Commit
            self.session.commit()
            
            logger.info(f"✓ Snapshot captured:")
            logger.info(f"  Portfolio: {portfolio.name}")
            logger.info(f"  Positions: {len(positions)}")
            logger.info(f"  Greeks history: {greeks_captured} positions")
            logger.info(f"  Total Equity: ${portfolio.total_equity:,.2f}")
            logger.info(f"  Delta: {portfolio.portfolio_greeks.delta:.2f}")
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to capture snapshot: {e}")
            logger.exception("Full error:")
            return False
    
    def _create_portfolio_snapshot(
        self,
        portfolio: dm.Portfolio,
        positions: List[dm.Position],
        trades: List[dm.Trade],
        snapshot_date: datetime
    ) -> DailyPerformanceORM:
        """Create portfolio-level daily snapshot"""
        try:
            # Calculate P&L
            realized_pnl = Decimal('0')
            unrealized_pnl = sum(p.unrealized_pnl() for p in positions)
            
            # Count open trades
            num_trades = len(trades) if trades else 0
            open_trades = len([t for t in trades if t.is_open]) if trades else 0
            
            # Check if snapshot already exists for today
            existing = self.session.query(DailyPerformanceORM).filter_by(
                portfolio_id=portfolio.id,
                date=snapshot_date
            ).first()
            
            if existing:
                logger.info(f"Updating existing snapshot for {snapshot_date.date()}")
                # Update existing
                existing.total_equity = portfolio.total_equity
                existing.cash_balance = portfolio.cash_balance
                existing.daily_pnl = portfolio.daily_pnl
                existing.realized_pnl = realized_pnl
                existing.unrealized_pnl = unrealized_pnl
                existing.num_positions = len(positions)
                existing.num_trades = open_trades
                
                if portfolio.portfolio_greeks:
                    existing.portfolio_delta = portfolio.portfolio_greeks.delta
                    existing.portfolio_theta = portfolio.portfolio_greeks.theta
                    existing.portfolio_vega = portfolio.portfolio_greeks.vega
                
                return existing
            
            # Create new snapshot
            snapshot = DailyPerformanceORM(
                id=str(dm.uuid.uuid4()),
                portfolio_id=portfolio.id,
                date=snapshot_date,
                total_equity=portfolio.total_equity,
                cash_balance=portfolio.cash_balance,
                daily_pnl=portfolio.daily_pnl,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                num_positions=len(positions),
                num_trades=open_trades,
                created_at=datetime.utcnow()
            )
            
            # Add Greeks if available
            if portfolio.portfolio_greeks:
                snapshot.portfolio_delta = portfolio.portfolio_greeks.delta
                snapshot.portfolio_theta = portfolio.portfolio_greeks.theta
                snapshot.portfolio_vega = portfolio.portfolio_greeks.vega
            
            self.session.add(snapshot)
            self.session.flush()
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error creating portfolio snapshot: {e}")
            return None
    
    def _capture_greeks_history(
        self,
        positions: List[dm.Position],
        snapshot_date: datetime
    ) -> int:
        """
        Capture Greeks history for all positions
        
        This enables:
        - Greeks evolution over time
        - P&L attribution by Greek
        - Identifying when Greeks changed significantly
        """
        captured = 0
        
        for position in positions:
            try:
                if not position.greeks:
                    continue
                
                # Check if already captured today
                existing = self.session.query(GreeksHistoryORM).filter_by(
                    position_id=position.id,
                    timestamp=snapshot_date
                ).first()
                
                if existing:
                    # Update existing
                    existing.delta = position.greeks.delta
                    existing.gamma = position.greeks.gamma
                    existing.theta = position.greeks.theta
                    existing.vega = position.greeks.vega
                    existing.rho = position.greeks.rho
                    existing.underlying_price = position.current_price
                    captured += 1
                    continue
                
                # Create new history entry
                history = GreeksHistoryORM(
                    id=str(dm.uuid.uuid4()),
                    position_id=position.id,
                    timestamp=snapshot_date,
                    delta=position.greeks.delta,
                    gamma=position.greeks.gamma,
                    theta=position.greeks.theta,
                    vega=position.greeks.vega,
                    rho=position.greeks.rho,
                    underlying_price=position.current_price,
                    created_at=datetime.utcnow()
                )
                
                self.session.add(history)
                captured += 1
                
            except Exception as e:
                logger.warning(f"Failed to capture Greeks for position {position.id}: {e}")
                continue
        
        self.session.flush()
        return captured
    
    def capture_all_portfolio_snapshots(self) -> Dict[str, bool]:
        """
        Capture daily snapshots for ALL active portfolios directly from ORM.

        Called by the workflow engine in REPORTING state and during monitoring.
        Works directly with ORM objects — no domain conversion needed.

        Returns:
            Dict mapping portfolio name → success bool
        """
        results = {}
        snapshot_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            # Get all non-deprecated portfolios
            portfolios = self.session.query(PortfolioORM).filter(
                ~PortfolioORM.tags.contains('"deprecated"')
            ).all()

            # SQLite JSON contains workaround — filter in Python
            active_portfolios = []
            for p in portfolios:
                tags = p.tags or []
                if 'deprecated' not in tags:
                    active_portfolios.append(p)

            logger.info(f"Capturing snapshots for {len(active_portfolios)} portfolios")

            for portfolio_orm in active_portfolios:
                try:
                    success = self._capture_portfolio_snapshot_from_orm(
                        portfolio_orm, snapshot_date
                    )
                    results[portfolio_orm.name] = success
                    if success:
                        logger.info(f"  Snapshot: {portfolio_orm.name} — OK")
                    else:
                        logger.warning(f"  Snapshot: {portfolio_orm.name} — FAILED")
                except Exception as e:
                    logger.error(f"  Snapshot error for {portfolio_orm.name}: {e}")
                    results[portfolio_orm.name] = False

            self.session.commit()
            logger.info(
                f"Snapshots captured: {sum(results.values())}/{len(results)} portfolios"
            )

        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to capture portfolio snapshots: {e}")

        return results

    def _capture_portfolio_snapshot_from_orm(
        self, portfolio_orm: PortfolioORM, snapshot_date: datetime
    ) -> bool:
        """Capture a single portfolio snapshot directly from ORM data."""
        from trading_cotrader.core.database.schema import TradeORM

        portfolio_id = portfolio_orm.id
        equity = portfolio_orm.total_equity or Decimal('0')
        cash = portfolio_orm.cash_balance or Decimal('0')
        daily_pnl = portfolio_orm.daily_pnl or Decimal('0')
        realized = portfolio_orm.realized_pnl or Decimal('0')
        unrealized = portfolio_orm.unrealized_pnl or Decimal('0')

        # Position count
        positions = portfolio_orm.positions or []
        num_positions = len(positions)

        # Open trade count
        open_trades = self.session.query(TradeORM).filter(
            TradeORM.portfolio_id == portfolio_id,
            TradeORM.is_open == True,
        ).count()

        # Upsert daily snapshot
        existing = self.session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_id,
            date=snapshot_date,
        ).first()

        if existing:
            existing.total_equity = equity
            existing.cash_balance = cash
            existing.daily_pnl = daily_pnl
            existing.realized_pnl = realized
            existing.unrealized_pnl = unrealized
            existing.num_positions = num_positions
            existing.num_trades = open_trades
            existing.portfolio_delta = portfolio_orm.portfolio_delta
            existing.portfolio_gamma = portfolio_orm.portfolio_gamma
            existing.portfolio_theta = portfolio_orm.portfolio_theta
            existing.portfolio_vega = portfolio_orm.portfolio_vega
            existing.var_1d_95 = portfolio_orm.var_1d_95
            existing.var_1d_99 = portfolio_orm.var_1d_99
        else:
            snapshot = DailyPerformanceORM(
                id=str(dm.uuid.uuid4()),
                portfolio_id=portfolio_id,
                date=snapshot_date,
                total_equity=equity,
                cash_balance=cash,
                daily_pnl=daily_pnl,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                num_positions=num_positions,
                num_trades=open_trades,
                portfolio_delta=portfolio_orm.portfolio_delta,
                portfolio_gamma=portfolio_orm.portfolio_gamma,
                portfolio_theta=portfolio_orm.portfolio_theta,
                portfolio_vega=portfolio_orm.portfolio_vega,
                var_1d_95=portfolio_orm.var_1d_95,
                var_1d_99=portfolio_orm.var_1d_99,
                created_at=datetime.utcnow(),
            )
            self.session.add(snapshot)

        # Capture Greeks history for each position
        for pos_orm in positions:
            self._capture_position_greeks_from_orm(pos_orm, snapshot_date)

        self.session.flush()
        return True

    def _capture_position_greeks_from_orm(
        self, pos_orm: PositionORM, snapshot_date: datetime
    ) -> None:
        """Capture Greeks history for a single position from ORM."""
        if not pos_orm.delta and not pos_orm.theta:
            return  # No Greeks data

        existing = self.session.query(GreeksHistoryORM).filter_by(
            position_id=pos_orm.id,
            timestamp=snapshot_date,
        ).first()

        if existing:
            existing.delta = pos_orm.delta
            existing.gamma = pos_orm.gamma
            existing.theta = pos_orm.theta
            existing.vega = pos_orm.vega
            existing.rho = pos_orm.rho
            existing.underlying_price = pos_orm.current_underlying_price
        else:
            history = GreeksHistoryORM(
                id=str(dm.uuid.uuid4()),
                position_id=pos_orm.id,
                timestamp=snapshot_date,
                delta=pos_orm.delta,
                gamma=pos_orm.gamma,
                theta=pos_orm.theta,
                vega=pos_orm.vega,
                rho=pos_orm.rho,
                underlying_price=pos_orm.current_underlying_price,
                created_at=datetime.utcnow(),
            )
            self.session.add(history)

    def get_portfolio_history(
        self,
        portfolio_id: str,
        days: int = 30
    ) -> List[DailyPerformanceORM]:
        """
        Get portfolio snapshots for the last N days
        
        Use this for:
        - Plotting equity curve
        - Tracking delta evolution
        - Calculating win streaks
        """
        try:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            snapshots = self.session.query(DailyPerformanceORM).filter(
                DailyPerformanceORM.portfolio_id == portfolio_id,
                DailyPerformanceORM.date >= cutoff
            ).order_by(DailyPerformanceORM.date).all()
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}")
            return []
    
    def get_position_greeks_history(
        self,
        position_id: str,
        days: int = 30
    ) -> List[GreeksHistoryORM]:
        """
        Get Greeks evolution for a position
        
        Use this for:
        - Seeing how delta changed as underlying moved
        - P&L attribution (theta decay vs delta move)
        - Identifying adjustment opportunities
        """
        try:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            history = self.session.query(GreeksHistoryORM).filter(
                GreeksHistoryORM.position_id == position_id,
                GreeksHistoryORM.timestamp >= cutoff
            ).order_by(GreeksHistoryORM.timestamp).all()
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting Greeks history: {e}")
            return []
    
    def get_summary_stats(self, portfolio_id: str, days: int = 30) -> Dict:
        """
        Get summary statistics from snapshots
        
        Returns insights like:
        - Average daily P&L
        - Max delta this period
        - Equity high/low
        - Win rate
        """
        try:
            snapshots = self.get_portfolio_history(portfolio_id, days)
            
            if not snapshots:
                return {}
            
            # Calculate stats
            daily_pnls = [float(s.daily_pnl) for s in snapshots if s.daily_pnl]
            equities = [float(s.total_equity) for s in snapshots]
            deltas = [float(s.portfolio_delta) for s in snapshots if s.portfolio_delta]
            
            stats = {
                'days_tracked': len(snapshots),
                'avg_daily_pnl': sum(daily_pnls) / len(daily_pnls) if daily_pnls else 0,
                'total_pnl': sum(daily_pnls) if daily_pnls else 0,
                'winning_days': len([p for p in daily_pnls if p > 0]),
                'losing_days': len([p for p in daily_pnls if p < 0]),
                'max_equity': max(equities) if equities else 0,
                'min_equity': min(equities) if equities else 0,
                'current_equity': equities[-1] if equities else 0,
                'avg_delta': sum(deltas) / len(deltas) if deltas else 0,
                'max_delta': max(deltas) if deltas else 0,
                'min_delta': min(deltas) if deltas else 0,
            }
            
            # Win rate
            if daily_pnls:
                stats['win_rate'] = (stats['winning_days'] / len(daily_pnls)) * 100
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating summary stats: {e}")
            return {}


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":

    
    setup_logging()
    
    with session_scope() as session:
        # Get portfolio
        portfolio_repo = PortfolioRepository(session)
        portfolios = portfolio_repo.get_all_portfolios()
        
        if not portfolios:
            print("No portfolios found. Run sync first.")
            exit(1)
        
        portfolio = portfolios[0]
        
        # Get positions
        position_repo = PositionRepository(session)
        positions = position_repo.get_by_portfolio(portfolio.id)
        
        # Capture snapshot
        snapshot_service = SnapshotService(session)
        success = snapshot_service.capture_daily_snapshot(portfolio, positions)
        
        if success:
            print("\n✅ Snapshot captured successfully!")
            
            # Show summary stats
            stats = snapshot_service.get_summary_stats(portfolio.id, days=30)
            if stats:
                print(f"\n📊 Summary Stats (last {stats['days_tracked']} days):")
                print(f"  Total P&L: ${stats['total_pnl']:,.2f}")
                print(f"  Avg Daily P&L: ${stats['avg_daily_pnl']:,.2f}")
                print(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
                print(f"  Avg Delta: {stats['avg_delta']:.2f}")
        else:
            print("❌ Snapshot failed")