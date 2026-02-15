"""
Performance Metrics Service - Portfolio and strategy-level analytics.

Calculates OptionsKit-style performance metrics from trade history:
    - Total P&L, win rate, profit factor, expectancy
    - Avg win/loss, biggest win/loss
    - Max drawdown, CAGR, Sharpe ratio, MAR ratio
    - Strategy breakdown, weekly/monthly P&L

Usage:
    from trading_cotrader.services.performance_metrics_service import PerformanceMetricsService
    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        svc = PerformanceMetricsService(session)
        metrics = svc.calculate_portfolio_metrics(portfolio_id)
        breakdown = svc.calculate_strategy_breakdown(portfolio_id)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
import math
import logging

from sqlalchemy.orm import Session

from trading_cotrader.core.database.schema import TradeORM, StrategyORM, DailyPerformanceORM

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Complete performance metrics for a portfolio or strategy slice."""
    # Identity
    label: str = ""                     # Portfolio name or strategy type
    portfolio_id: str = ""

    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    # P&L
    total_pnl: Decimal = Decimal('0')
    total_wins: Decimal = Decimal('0')
    total_losses: Decimal = Decimal('0')
    avg_win: Decimal = Decimal('0')
    avg_loss: Decimal = Decimal('0')
    biggest_win: Decimal = Decimal('0')
    biggest_loss: Decimal = Decimal('0')

    # Ratios
    win_rate: float = 0.0               # percentage
    profit_factor: float = 0.0          # total_wins / abs(total_losses)
    expectancy: Decimal = Decimal('0')  # avg P&L per trade

    # Risk-adjusted
    max_drawdown_pct: float = 0.0
    cagr_pct: float = 0.0
    sharpe_ratio: float = 0.0
    mar_ratio: float = 0.0             # CAGR / max_drawdown

    # Capital
    initial_capital: Decimal = Decimal('0')
    current_equity: Decimal = Decimal('0')
    return_pct: float = 0.0

    def to_summary_row(self) -> List:
        """Return a flat list for tabulate display."""
        return [
            self.label,
            self.total_trades,
            f"{self.win_rate:.1f}%",
            f"${float(self.total_pnl):,.2f}",
            f"${float(self.avg_win):,.2f}" if self.winning_trades else "-",
            f"${float(self.avg_loss):,.2f}" if self.losing_trades else "-",
            f"{self.profit_factor:.2f}" if self.profit_factor else "-",
            f"${float(self.expectancy):,.2f}",
            f"{self.max_drawdown_pct:.1f}%",
            f"{self.sharpe_ratio:.2f}" if self.sharpe_ratio else "-",
        ]


@dataclass
class StrategyBreakdown:
    """Performance breakdown by strategy type."""
    portfolio_label: str = ""
    strategies: Dict[str, PerformanceMetrics] = field(default_factory=dict)


@dataclass
class WeeklyPnL:
    """Weekly P&L entry."""
    week_start: datetime = field(default_factory=datetime.utcnow)
    week_end: datetime = field(default_factory=datetime.utcnow)
    pnl: Decimal = Decimal('0')
    trade_count: int = 0
    cumulative_pnl: Decimal = Decimal('0')


class PerformanceMetricsService:
    """Calculate performance metrics from trade history and daily snapshots."""

    def __init__(self, session: Session):
        self.session = session

    def calculate_portfolio_metrics(
        self,
        portfolio_id: str,
        label: str = "",
        initial_capital: Decimal = Decimal('0'),
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics for a portfolio.

        Queries all closed/expired trades for the portfolio and computes
        win rate, profit factor, expectancy, drawdown, etc.

        Args:
            portfolio_id: Portfolio UUID.
            label: Display label for this metrics set.
            initial_capital: Starting capital (for return %).

        Returns:
            PerformanceMetrics dataclass.
        """
        # Query closed trades
        closed_statuses = ['closed', 'expired', 'rolled']
        trades = (
            self.session.query(TradeORM)
            .filter(TradeORM.portfolio_id == portfolio_id)
            .filter(TradeORM.trade_status.in_(closed_statuses))
            .order_by(TradeORM.closed_at.asc())
            .all()
        )

        # Also include executed (open) trades for current P&L snapshot
        open_trades = (
            self.session.query(TradeORM)
            .filter(TradeORM.portfolio_id == portfolio_id)
            .filter(TradeORM.trade_status == 'executed')
            .all()
        )

        return self._compute_metrics(
            trades=trades,
            open_trades=open_trades,
            label=label,
            portfolio_id=portfolio_id,
            initial_capital=initial_capital,
        )

    def calculate_strategy_breakdown(
        self,
        portfolio_id: str,
        label: str = "",
    ) -> StrategyBreakdown:
        """
        Calculate per-strategy performance for a portfolio.

        Groups closed trades by strategy type and computes metrics for each.

        Args:
            portfolio_id: Portfolio UUID.
            label: Display label.

        Returns:
            StrategyBreakdown with a dict of strategy_type → PerformanceMetrics.
        """
        closed_statuses = ['closed', 'expired', 'rolled']
        trades = (
            self.session.query(TradeORM)
            .filter(TradeORM.portfolio_id == portfolio_id)
            .filter(TradeORM.trade_status.in_(closed_statuses))
            .order_by(TradeORM.closed_at.asc())
            .all()
        )

        # Group by strategy type
        by_strategy: Dict[str, List[TradeORM]] = {}
        for trade in trades:
            strategy_type = self._get_strategy_type(trade)
            by_strategy.setdefault(strategy_type, []).append(trade)

        breakdown = StrategyBreakdown(portfolio_label=label)
        for strategy_type, strategy_trades in by_strategy.items():
            breakdown.strategies[strategy_type] = self._compute_metrics(
                trades=strategy_trades,
                open_trades=[],
                label=strategy_type,
                portfolio_id=portfolio_id,
            )

        return breakdown

    def calculate_weekly_performance(
        self,
        portfolio_id: str,
        weeks: int = 12,
    ) -> List[WeeklyPnL]:
        """
        Calculate weekly P&L for the last N weeks.

        Uses daily snapshots if available, otherwise aggregates trade P&L.

        Args:
            portfolio_id: Portfolio UUID.
            weeks: Number of weeks to look back.

        Returns:
            List of WeeklyPnL entries, oldest first.
        """
        cutoff = datetime.utcnow() - timedelta(weeks=weeks)

        # Try daily snapshots first
        snapshots = (
            self.session.query(DailyPerformanceORM)
            .filter(DailyPerformanceORM.portfolio_id == portfolio_id)
            .filter(DailyPerformanceORM.date >= cutoff)
            .order_by(DailyPerformanceORM.date.asc())
            .all()
        )

        if snapshots:
            return self._weekly_from_snapshots(snapshots)

        # Fallback: aggregate from closed trades
        closed_statuses = ['closed', 'expired', 'rolled']
        trades = (
            self.session.query(TradeORM)
            .filter(TradeORM.portfolio_id == portfolio_id)
            .filter(TradeORM.trade_status.in_(closed_statuses))
            .filter(TradeORM.closed_at >= cutoff)
            .order_by(TradeORM.closed_at.asc())
            .all()
        )

        return self._weekly_from_trades(trades)

    def calculate_all_portfolios_summary(
        self,
        portfolio_ids_and_labels: List[Dict],
    ) -> List[PerformanceMetrics]:
        """
        Calculate metrics for multiple portfolios.

        Args:
            portfolio_ids_and_labels: List of dicts with 'id', 'label', 'initial_capital'.

        Returns:
            List of PerformanceMetrics, one per portfolio.
        """
        results = []
        for info in portfolio_ids_and_labels:
            metrics = self.calculate_portfolio_metrics(
                portfolio_id=info['id'],
                label=info.get('label', ''),
                initial_capital=Decimal(str(info.get('initial_capital', 0))),
            )
            results.append(metrics)
        return results

    # =========================================================================
    # Internal computation
    # =========================================================================

    def _compute_metrics(
        self,
        trades: List[TradeORM],
        open_trades: List[TradeORM],
        label: str,
        portfolio_id: str,
        initial_capital: Decimal = Decimal('0'),
    ) -> PerformanceMetrics:
        """Core metrics computation from a list of trades."""
        m = PerformanceMetrics(
            label=label,
            portfolio_id=portfolio_id,
            initial_capital=initial_capital,
        )

        if not trades and not open_trades:
            return m

        # Collect P&L values from closed trades
        pnl_values: List[Decimal] = []
        for trade in trades:
            pnl = Decimal(str(trade.total_pnl or 0))
            pnl_values.append(pnl)

        m.total_trades = len(pnl_values)

        if not pnl_values:
            # Only open trades, no closed history
            m.total_pnl = sum(
                Decimal(str(t.total_pnl or 0)) for t in open_trades
            )
            m.current_equity = initial_capital + m.total_pnl
            if initial_capital > 0:
                m.return_pct = float(m.total_pnl / initial_capital * 100)
            return m

        # Wins / losses
        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]
        breakevens = [p for p in pnl_values if p == 0]

        m.winning_trades = len(wins)
        m.losing_trades = len(losses)
        m.breakeven_trades = len(breakevens)

        m.total_wins = sum(wins) if wins else Decimal('0')
        m.total_losses = sum(losses) if losses else Decimal('0')
        m.total_pnl = sum(pnl_values)

        m.avg_win = m.total_wins / len(wins) if wins else Decimal('0')
        m.avg_loss = m.total_losses / len(losses) if losses else Decimal('0')
        m.biggest_win = max(wins) if wins else Decimal('0')
        m.biggest_loss = min(losses) if losses else Decimal('0')

        # Win rate
        if m.total_trades > 0:
            m.win_rate = (m.winning_trades / m.total_trades) * 100

        # Profit factor
        if m.total_losses != 0:
            m.profit_factor = float(abs(m.total_wins / m.total_losses))

        # Expectancy (avg P&L per trade)
        if m.total_trades > 0:
            m.expectancy = m.total_pnl / m.total_trades

        # Include unrealized P&L from open trades
        unrealized = sum(Decimal(str(t.total_pnl or 0)) for t in open_trades)
        m.current_equity = initial_capital + m.total_pnl + unrealized

        # Return %
        if initial_capital > 0:
            m.return_pct = float((m.total_pnl + unrealized) / initial_capital * 100)

        # Max drawdown from equity curve
        m.max_drawdown_pct = self._calculate_max_drawdown(pnl_values, initial_capital)

        # CAGR
        m.cagr_pct = self._calculate_cagr(trades, initial_capital, m.total_pnl)

        # Sharpe ratio (simplified — daily P&L std dev)
        m.sharpe_ratio = self._calculate_sharpe(pnl_values, initial_capital)

        # MAR ratio
        if m.max_drawdown_pct > 0:
            m.mar_ratio = m.cagr_pct / m.max_drawdown_pct

        return m

    def _calculate_max_drawdown(
        self,
        pnl_values: List[Decimal],
        initial_capital: Decimal,
    ) -> float:
        """Calculate max drawdown % from a sequence of P&L values."""
        if not pnl_values or initial_capital <= 0:
            return 0.0

        # Build equity curve
        equity = float(initial_capital)
        peak = equity
        max_dd = 0.0

        for pnl in pnl_values:
            equity += float(pnl)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_cagr(
        self,
        trades: List[TradeORM],
        initial_capital: Decimal,
        total_pnl: Decimal,
    ) -> float:
        """Calculate compound annual growth rate."""
        if not trades or initial_capital <= 0:
            return 0.0

        # Determine time span
        first_date = None
        last_date = None
        for t in trades:
            dt = t.closed_at or t.opened_at or t.created_at
            if dt:
                if first_date is None or dt < first_date:
                    first_date = dt
                if last_date is None or dt > last_date:
                    last_date = dt

        if not first_date or not last_date:
            return 0.0

        days = (last_date - first_date).days
        if days < 1:
            return 0.0

        years = days / 365.25
        ending_value = float(initial_capital + total_pnl)
        beginning_value = float(initial_capital)

        if beginning_value <= 0 or ending_value <= 0:
            return 0.0

        try:
            cagr = (math.pow(ending_value / beginning_value, 1 / years) - 1) * 100
        except (ValueError, ZeroDivisionError, OverflowError):
            cagr = 0.0

        return cagr

    def _calculate_sharpe(
        self,
        pnl_values: List[Decimal],
        initial_capital: Decimal,
        risk_free_rate: float = 0.05,
    ) -> float:
        """
        Simplified Sharpe ratio from trade returns.

        Uses per-trade returns as proxy for periodic returns.
        Annualizes assuming ~252 trading days and ~20 trades/month.
        """
        if len(pnl_values) < 2 or initial_capital <= 0:
            return 0.0

        # Convert to per-trade return %
        returns = [float(pnl / initial_capital) for pnl in pnl_values]

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        if std_dev == 0:
            return 0.0

        # Annualize (assume ~50 trades per year as a rough baseline)
        trades_per_year = min(len(pnl_values) * 4, 250)  # rough annualization
        annualized_return = avg_return * trades_per_year
        annualized_std = std_dev * math.sqrt(trades_per_year)

        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return sharpe

    def _get_strategy_type(self, trade: TradeORM) -> str:
        """Get strategy type string from a trade ORM."""
        if trade.strategy_id:
            strategy = (
                self.session.query(StrategyORM)
                .filter_by(id=trade.strategy_id)
                .first()
            )
            if strategy:
                return strategy.strategy_type or 'unknown'
        return 'unknown'

    def _weekly_from_snapshots(
        self,
        snapshots: List[DailyPerformanceORM],
    ) -> List[WeeklyPnL]:
        """Aggregate daily snapshots into weekly buckets."""
        if not snapshots:
            return []

        weekly: Dict[str, WeeklyPnL] = {}
        cumulative = Decimal('0')

        for snap in snapshots:
            # ISO week key
            dt = snap.date
            week_key = dt.strftime('%Y-W%W')
            monday = dt - timedelta(days=dt.weekday())

            if week_key not in weekly:
                weekly[week_key] = WeeklyPnL(
                    week_start=monday,
                    week_end=monday + timedelta(days=6),
                )

            daily_pnl = Decimal(str(snap.daily_pnl or 0))
            weekly[week_key].pnl += daily_pnl
            weekly[week_key].trade_count += 1
            cumulative += daily_pnl
            weekly[week_key].cumulative_pnl = cumulative

        return sorted(weekly.values(), key=lambda w: w.week_start)

    def _weekly_from_trades(self, trades: List[TradeORM]) -> List[WeeklyPnL]:
        """Aggregate trade P&L into weekly buckets."""
        if not trades:
            return []

        weekly: Dict[str, WeeklyPnL] = {}
        cumulative = Decimal('0')

        for trade in trades:
            dt = trade.closed_at or trade.created_at
            week_key = dt.strftime('%Y-W%W')
            monday = dt - timedelta(days=dt.weekday())

            if week_key not in weekly:
                weekly[week_key] = WeeklyPnL(
                    week_start=monday,
                    week_end=monday + timedelta(days=6),
                )

            pnl = Decimal(str(trade.total_pnl or 0))
            weekly[week_key].pnl += pnl
            weekly[week_key].trade_count += 1
            cumulative += pnl
            weekly[week_key].cumulative_pnl = cumulative

        return sorted(weekly.values(), key=lambda w: w.week_start)
