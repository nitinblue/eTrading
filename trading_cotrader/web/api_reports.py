"""
Reports API Router — Pre-built report endpoints for the React frontend.

Mounted in approval_api.py at /api/reports prefix.
Reuses PerformanceMetricsService for portfolio/strategy/source metrics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
import logging

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import func

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import (
    PortfolioORM,
    TradeORM,
    LegORM,
    StrategyORM,
    RecommendationORM,
    DecisionLogORM,
    DailyPerformanceORM,
    GreeksHistoryORM,
    TradeEventORM,
)
from trading_cotrader.services.performance_metrics_service import (
    PerformanceMetricsService,
    PerformanceMetrics,
    WeeklyPnL,
)

logger = logging.getLogger(__name__)


def _dec(val: Any) -> float:
    if val is None:
        return 0.0
    return float(val)


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _metrics_to_dict(m: PerformanceMetrics) -> dict:
    """Convert PerformanceMetrics dataclass to JSON-safe dict."""
    return {
        'label': m.label,
        'portfolio_id': m.portfolio_id,
        'total_trades': m.total_trades,
        'winning_trades': m.winning_trades,
        'losing_trades': m.losing_trades,
        'breakeven_trades': m.breakeven_trades,
        'total_pnl': _dec(m.total_pnl),
        'total_wins': _dec(m.total_wins),
        'total_losses': _dec(m.total_losses),
        'avg_win': _dec(m.avg_win),
        'avg_loss': _dec(m.avg_loss),
        'biggest_win': _dec(m.biggest_win),
        'biggest_loss': _dec(m.biggest_loss),
        'win_rate': round(m.win_rate, 2),
        'profit_factor': round(m.profit_factor, 2),
        'expectancy': _dec(m.expectancy),
        'max_drawdown_pct': round(m.max_drawdown_pct, 2),
        'cagr_pct': round(m.cagr_pct, 2),
        'sharpe_ratio': round(m.sharpe_ratio, 2),
        'mar_ratio': round(m.mar_ratio, 2),
        'initial_capital': _dec(m.initial_capital),
        'current_equity': _dec(m.current_equity),
        'return_pct': round(m.return_pct, 2),
    }


def _weekly_to_dict(w: WeeklyPnL) -> dict:
    return {
        'week_start': _iso(w.week_start),
        'week_end': _iso(w.week_end),
        'pnl': _dec(w.pnl),
        'trade_count': w.trade_count,
        'cumulative_pnl': _dec(w.cumulative_pnl),
    }


def create_reports_router() -> APIRouter:
    """Create the reports API router."""

    router = APIRouter()

    # ------------------------------------------------------------------
    # Trade Journal
    # ------------------------------------------------------------------

    @router.get("/trade-journal")
    async def trade_journal(
        portfolio: Optional[str] = Query(None),
        status: Optional[str] = Query(None, description="open, closed, all"),
        date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
        date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
        source: Optional[str] = Query(None),
        strategy: Optional[str] = Query(None),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """All trades with P&L, legs, strategy, source — the trade journal."""
        with session_scope() as session:
            q = session.query(TradeORM).order_by(TradeORM.created_at.desc())

            if portfolio:
                p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
                if p:
                    q = q.filter(TradeORM.portfolio_id == p.id)

            if status == 'open':
                q = q.filter(TradeORM.is_open == True)
            elif status == 'closed':
                q = q.filter(TradeORM.is_open == False)

            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from)
                    q = q.filter(TradeORM.created_at >= dt_from)
                except ValueError:
                    pass
            if date_to:
                try:
                    dt_to = datetime.fromisoformat(date_to)
                    q = q.filter(TradeORM.created_at <= dt_to + timedelta(days=1))
                except ValueError:
                    pass

            if source:
                q = q.filter(TradeORM.trade_source == source)
            if strategy:
                strat = session.query(StrategyORM).filter(StrategyORM.strategy_type == strategy).first()
                if strat:
                    q = q.filter(TradeORM.strategy_id == strat.id)

            total = q.count()
            trades = q.offset(offset).limit(limit).all()

            rows = []
            for t in trades:
                duration_days = None
                if t.opened_at and t.closed_at:
                    duration_days = (t.closed_at - t.opened_at).days
                elif t.opened_at:
                    duration_days = (datetime.utcnow() - t.opened_at).days

                rows.append({
                    'id': t.id,
                    'portfolio_name': t.portfolio.name if t.portfolio else '',
                    'strategy_type': t.strategy.strategy_type if t.strategy else None,
                    'underlying_symbol': t.underlying_symbol,
                    'trade_type': t.trade_type,
                    'trade_status': t.trade_status,
                    'trade_source': t.trade_source,
                    'is_open': t.is_open,
                    'legs_count': len(t.legs) if t.legs else 0,
                    'entry_price': _dec(t.entry_price),
                    'exit_price': _dec(t.exit_price),
                    'total_pnl': _dec(t.total_pnl),
                    'delta_pnl': _dec(t.delta_pnl),
                    'theta_pnl': _dec(t.theta_pnl),
                    'vega_pnl': _dec(t.vega_pnl),
                    'max_risk': _dec(t.max_risk),
                    'duration_days': duration_days,
                    'created_at': _iso(t.created_at),
                    'opened_at': _iso(t.opened_at),
                    'closed_at': _iso(t.closed_at),
                    'notes': t.notes,
                    'rolled_from_id': t.rolled_from_id,
                    'rolled_to_id': t.rolled_to_id,
                })

            return {'total': total, 'trades': rows}

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    @router.get("/performance")
    async def performance_report(
        portfolio: Optional[str] = Query(None, description="Portfolio name, or omit for all"),
    ):
        """Portfolio performance metrics (win rate, Sharpe, drawdown, etc.)."""
        with session_scope() as session:
            if portfolio:
                p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
                if not p:
                    raise HTTPException(404, f"Portfolio '{portfolio}' not found")
                svc = PerformanceMetricsService(session)
                metrics = svc.calculate_portfolio_metrics(
                    p.id, label=p.name,
                    initial_capital=Decimal(str(p.initial_capital or 0)),
                )
                return [_metrics_to_dict(metrics)]
            else:
                portfolios = (
                    session.query(PortfolioORM)
                    .filter(PortfolioORM.portfolio_type != 'deprecated')
                    .order_by(PortfolioORM.name)
                    .all()
                )
                svc = PerformanceMetricsService(session)
                infos = [
                    {'id': p.id, 'label': p.name, 'initial_capital': p.initial_capital or 0}
                    for p in portfolios
                ]
                results = svc.calculate_all_portfolios_summary(infos)
                return [_metrics_to_dict(m) for m in results]

    # ------------------------------------------------------------------
    # Strategy Breakdown
    # ------------------------------------------------------------------

    @router.get("/strategy-breakdown")
    async def strategy_breakdown(
        portfolio: str = Query(..., description="Portfolio name (required)"),
    ):
        """Per-strategy performance metrics for a portfolio."""
        with session_scope() as session:
            p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
            if not p:
                raise HTTPException(404, f"Portfolio '{portfolio}' not found")
            svc = PerformanceMetricsService(session)
            breakdown = svc.calculate_strategy_breakdown(p.id, label=p.name)
            return {
                'portfolio': p.name,
                'strategies': {
                    k: _metrics_to_dict(v)
                    for k, v in breakdown.strategies.items()
                },
            }

    # ------------------------------------------------------------------
    # Source Attribution
    # ------------------------------------------------------------------

    @router.get("/source-attribution")
    async def source_attribution(
        portfolio: str = Query(..., description="Portfolio name (required)"),
    ):
        """Per-source performance metrics (screener vs manual vs AI)."""
        with session_scope() as session:
            p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
            if not p:
                raise HTTPException(404, f"Portfolio '{portfolio}' not found")
            svc = PerformanceMetricsService(session)
            by_source = svc.calculate_source_breakdown(p.id, label=p.name)
            return {
                'portfolio': p.name,
                'sources': {
                    k: _metrics_to_dict(v)
                    for k, v in by_source.items()
                },
            }

    # ------------------------------------------------------------------
    # Weekly P&L
    # ------------------------------------------------------------------

    @router.get("/weekly-pnl")
    async def weekly_pnl(
        portfolio: str = Query(..., description="Portfolio name (required)"),
        weeks: int = Query(12, ge=1, le=52),
    ):
        """Weekly P&L buckets for a portfolio."""
        with session_scope() as session:
            p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
            if not p:
                raise HTTPException(404, f"Portfolio '{portfolio}' not found")
            svc = PerformanceMetricsService(session)
            weekly = svc.calculate_weekly_performance(p.id, weeks=weeks)
            return {
                'portfolio': p.name,
                'weeks': [_weekly_to_dict(w) for w in weekly],
            }

    # ------------------------------------------------------------------
    # Decision Audit
    # ------------------------------------------------------------------

    @router.get("/decisions")
    async def decision_audit(
        decision_type: Optional[str] = Query(None),
        response: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None),
        date_to: Optional[str] = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """Decision log with response times and patterns."""
        with session_scope() as session:
            q = session.query(DecisionLogORM).order_by(DecisionLogORM.presented_at.desc())

            if decision_type:
                q = q.filter(DecisionLogORM.decision_type == decision_type)
            if response:
                q = q.filter(DecisionLogORM.response == response)
            if date_from:
                try:
                    q = q.filter(DecisionLogORM.presented_at >= datetime.fromisoformat(date_from))
                except ValueError:
                    pass
            if date_to:
                try:
                    q = q.filter(DecisionLogORM.presented_at <= datetime.fromisoformat(date_to) + timedelta(days=1))
                except ValueError:
                    pass

            total = q.count()
            entries = q.offset(offset).limit(limit).all()

            return {
                'total': total,
                'decisions': [
                    {
                        'id': d.id,
                        'recommendation_id': d.recommendation_id,
                        'decision_type': d.decision_type,
                        'presented_at': _iso(d.presented_at),
                        'responded_at': _iso(d.responded_at),
                        'response': d.response,
                        'rationale': d.rationale,
                        'escalation_count': d.escalation_count,
                        'time_to_decision_seconds': d.time_to_decision_seconds,
                    }
                    for d in entries
                ],
            }

    # ------------------------------------------------------------------
    # Recommendations Report
    # ------------------------------------------------------------------

    @router.get("/recommendations")
    async def recommendations_report(
        status: Optional[str] = Query(None),
        source: Optional[str] = Query(None),
        underlying: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None),
        date_to: Optional[str] = Query(None),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """Full recommendation lifecycle with filters."""
        with session_scope() as session:
            q = session.query(RecommendationORM).order_by(RecommendationORM.created_at.desc())

            if status and status != 'all':
                q = q.filter(RecommendationORM.status == status)
            if source:
                q = q.filter(RecommendationORM.source == source)
            if underlying:
                q = q.filter(RecommendationORM.underlying == underlying)
            if date_from:
                try:
                    q = q.filter(RecommendationORM.created_at >= datetime.fromisoformat(date_from))
                except ValueError:
                    pass
            if date_to:
                try:
                    q = q.filter(RecommendationORM.created_at <= datetime.fromisoformat(date_to) + timedelta(days=1))
                except ValueError:
                    pass

            total = q.count()
            recs = q.offset(offset).limit(limit).all()

            return {
                'total': total,
                'recommendations': [
                    {
                        'id': r.id,
                        'recommendation_type': r.recommendation_type,
                        'source': r.source,
                        'screener_name': r.screener_name,
                        'underlying': r.underlying,
                        'strategy_type': r.strategy_type,
                        'confidence': r.confidence,
                        'rationale': r.rationale,
                        'risk_category': r.risk_category,
                        'suggested_portfolio': r.suggested_portfolio,
                        'status': r.status,
                        'created_at': _iso(r.created_at),
                        'reviewed_at': _iso(r.reviewed_at),
                        'portfolio_name': r.portfolio_name,
                        'trade_id_to_close': r.trade_id_to_close,
                        'exit_action': r.exit_action,
                        'exit_urgency': r.exit_urgency,
                        'triggered_rules': r.triggered_rules,
                    }
                    for r in recs
                ],
            }

    # ------------------------------------------------------------------
    # Trade Events
    # ------------------------------------------------------------------

    @router.get("/trade-events")
    async def trade_events(
        trade_id: Optional[str] = Query(None),
        event_type: Optional[str] = Query(None),
        underlying: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None),
        date_to: Optional[str] = Query(None),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """Trade event timeline."""
        with session_scope() as session:
            q = session.query(TradeEventORM).order_by(TradeEventORM.timestamp.desc())

            if trade_id:
                q = q.filter(TradeEventORM.trade_id == trade_id)
            if event_type:
                q = q.filter(TradeEventORM.event_type == event_type)
            if underlying:
                q = q.filter(TradeEventORM.underlying_symbol == underlying)
            if date_from:
                try:
                    q = q.filter(TradeEventORM.timestamp >= datetime.fromisoformat(date_from))
                except ValueError:
                    pass
            if date_to:
                try:
                    q = q.filter(TradeEventORM.timestamp <= datetime.fromisoformat(date_to) + timedelta(days=1))
                except ValueError:
                    pass

            total = q.count()
            events = q.offset(offset).limit(limit).all()

            return {
                'total': total,
                'events': [
                    {
                        'event_id': e.event_id,
                        'trade_id': e.trade_id,
                        'event_type': e.event_type,
                        'timestamp': _iso(e.timestamp),
                        'strategy_type': e.strategy_type,
                        'underlying_symbol': e.underlying_symbol,
                        'net_credit_debit': _dec(e.net_credit_debit),
                        'entry_delta': _dec(e.entry_delta),
                        'entry_theta': _dec(e.entry_theta),
                        'market_context': e.market_context,
                        'outcome': e.outcome,
                        'tags': e.tags,
                    }
                    for e in events
                ],
            }

    # ------------------------------------------------------------------
    # Daily Snapshots
    # ------------------------------------------------------------------

    @router.get("/daily-snapshots")
    async def daily_snapshots(
        portfolio: Optional[str] = Query(None),
        days: int = Query(30, ge=1, le=365),
    ):
        """Daily performance snapshots."""
        with session_scope() as session:
            q = session.query(DailyPerformanceORM)

            if portfolio:
                p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
                if p:
                    q = q.filter(DailyPerformanceORM.portfolio_id == p.id)

            cutoff = datetime.utcnow() - timedelta(days=days)
            q = q.filter(DailyPerformanceORM.date >= cutoff).order_by(DailyPerformanceORM.date.asc())

            snapshots = q.all()
            return [
                {
                    'id': s.id,
                    'portfolio_id': s.portfolio_id,
                    'date': _iso(s.date),
                    'total_equity': _dec(s.total_equity),
                    'cash_balance': _dec(s.cash_balance),
                    'daily_pnl': _dec(s.daily_pnl),
                    'realized_pnl': _dec(s.realized_pnl),
                    'unrealized_pnl': _dec(s.unrealized_pnl),
                    'delta_pnl': _dec(s.delta_pnl),
                    'gamma_pnl': _dec(s.gamma_pnl),
                    'theta_pnl': _dec(s.theta_pnl),
                    'vega_pnl': _dec(s.vega_pnl),
                    'portfolio_delta': _dec(s.portfolio_delta),
                    'portfolio_gamma': _dec(s.portfolio_gamma),
                    'portfolio_theta': _dec(s.portfolio_theta),
                    'portfolio_vega': _dec(s.portfolio_vega),
                    'var_1d_95': _dec(s.var_1d_95),
                    'num_positions': s.num_positions,
                    'num_open_trades': s.num_open_trades,
                }
                for s in snapshots
            ]

    # ------------------------------------------------------------------
    # Greeks History
    # ------------------------------------------------------------------

    @router.get("/greeks-history")
    async def greeks_history(
        position_id: str = Query(..., description="Position ID (required)"),
        days: int = Query(30, ge=1, le=365),
    ):
        """Greeks history for a specific position."""
        with session_scope() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)
            entries = (
                session.query(GreeksHistoryORM)
                .filter(
                    GreeksHistoryORM.position_id == position_id,
                    GreeksHistoryORM.timestamp >= cutoff,
                )
                .order_by(GreeksHistoryORM.timestamp.asc())
                .all()
            )
            return [
                {
                    'id': e.id,
                    'position_id': e.position_id,
                    'timestamp': _iso(e.timestamp),
                    'delta': _dec(e.delta),
                    'gamma': _dec(e.gamma),
                    'theta': _dec(e.theta),
                    'vega': _dec(e.vega),
                    'rho': _dec(e.rho),
                    'underlying_price': _dec(e.underlying_price),
                    'option_price': _dec(e.option_price),
                    'implied_volatility': _dec(e.implied_volatility),
                }
                for e in entries
            ]

    return router
