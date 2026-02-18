"""
v2 API Router — Comprehensive endpoints for the React frontend.

Mounted in approval_api.py at /api/v2 prefix.
Existing /api/* endpoints remain unchanged.
"""

from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
import logging

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import func

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import (
    PortfolioORM,
    TradeORM,
    LegORM,
    StrategyORM,
    SymbolORM,
    RecommendationORM,
    DecisionLogORM,
    WorkflowStateORM,
    DailyPerformanceORM,
)

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


def _dec(val: Any) -> float:
    """Safely convert Decimal/None to float."""
    if val is None:
        return 0.0
    return float(val)


def _iso(dt: Any) -> Optional[str]:
    """Safely convert datetime to ISO string."""
    if dt is None:
        return None
    return dt.isoformat()


def _compute_dte(trade: TradeORM) -> Optional[int]:
    """Compute days to expiration from the nearest expiring leg."""
    if not trade.legs:
        return None
    today = date_cls.today()
    min_dte = None
    for leg in trade.legs:
        if leg.symbol and leg.symbol.expiration:
            exp = leg.symbol.expiration
            if isinstance(exp, datetime):
                exp = exp.date()
            dte = (exp - today).days
            if min_dte is None or dte < min_dte:
                min_dte = dte
    return min_dte


def _serialize_leg(leg: LegORM) -> dict:
    """Serialize a single leg ORM to dict."""
    sym = leg.symbol
    return {
        'id': leg.id,
        'symbol_ticker': sym.ticker if sym else '',
        'asset_type': sym.asset_type if sym else '',
        'option_type': sym.option_type if sym else None,
        'strike': _dec(sym.strike) if sym and sym.strike else None,
        'expiration': _iso(sym.expiration) if sym else None,
        'quantity': leg.quantity,
        'side': leg.side,
        'entry_price': _dec(leg.entry_price),
        'current_price': _dec(leg.current_price),
        'exit_price': _dec(leg.exit_price),
        'entry_delta': _dec(leg.entry_delta),
        'entry_gamma': _dec(leg.entry_gamma),
        'entry_theta': _dec(leg.entry_theta),
        'entry_vega': _dec(leg.entry_vega),
        'delta': _dec(leg.delta),
        'gamma': _dec(leg.gamma),
        'theta': _dec(leg.theta),
        'vega': _dec(leg.vega),
        'fees': _dec(leg.fees),
        'commission': _dec(leg.commission),
    }


def _serialize_trade(trade: TradeORM) -> dict:
    """Serialize a trade ORM with legs."""
    portfolio = trade.portfolio
    strategy = trade.strategy
    return {
        'id': trade.id,
        'portfolio_id': trade.portfolio_id,
        'portfolio_name': portfolio.name if portfolio else '',
        'strategy_type': strategy.strategy_type if strategy else None,
        'trade_type': trade.trade_type,
        'trade_status': trade.trade_status,
        'underlying_symbol': trade.underlying_symbol,
        'trade_source': trade.trade_source,
        'created_at': _iso(trade.created_at),
        'opened_at': _iso(trade.opened_at),
        'closed_at': _iso(trade.closed_at),
        'entry_price': _dec(trade.entry_price),
        'entry_underlying_price': _dec(trade.entry_underlying_price),
        'entry_iv': _dec(trade.entry_iv),
        'entry_delta': _dec(trade.entry_delta),
        'entry_gamma': _dec(trade.entry_gamma),
        'entry_theta': _dec(trade.entry_theta),
        'entry_vega': _dec(trade.entry_vega),
        'current_price': _dec(trade.current_price),
        'current_underlying_price': _dec(trade.current_underlying_price),
        'current_iv': _dec(trade.current_iv),
        'current_delta': _dec(trade.current_delta),
        'current_gamma': _dec(trade.current_gamma),
        'current_theta': _dec(trade.current_theta),
        'current_vega': _dec(trade.current_vega),
        'total_pnl': _dec(trade.total_pnl),
        'delta_pnl': _dec(trade.delta_pnl),
        'gamma_pnl': _dec(trade.gamma_pnl),
        'theta_pnl': _dec(trade.theta_pnl),
        'vega_pnl': _dec(trade.vega_pnl),
        'unexplained_pnl': _dec(trade.unexplained_pnl),
        'max_risk': _dec(trade.max_risk),
        'stop_loss': _dec(trade.stop_loss),
        'profit_target': _dec(trade.profit_target),
        'rolled_from_id': trade.rolled_from_id,
        'rolled_to_id': trade.rolled_to_id,
        'recommendation_id': trade.recommendation_id,
        'dte': _compute_dte(trade),
        'is_open': trade.is_open,
        'notes': trade.notes,
        'tags': trade.tags,
        'legs': [_serialize_leg(leg) for leg in (trade.legs or [])],
    }


def _serialize_portfolio(p: PortfolioORM, open_count: int = 0) -> dict:
    """Serialize a portfolio ORM."""
    equity = _dec(p.total_equity)
    cash = _dec(p.cash_balance)
    initial = _dec(p.initial_capital)
    deployed_pct = ((equity - cash) / equity * 100) if equity else 0

    # Determine currency from broker name
    currency = 'USD'
    broker = (p.broker or '').lower()
    if 'zerodha' in broker or 'stallion' in broker:
        currency = 'INR'

    return {
        'id': p.id,
        'name': p.name,
        'portfolio_type': p.portfolio_type,
        'broker': p.broker,
        'account_id': p.account_id,
        'currency': currency,
        'initial_capital': initial,
        'cash_balance': cash,
        'buying_power': _dec(p.buying_power),
        'total_equity': equity,
        'portfolio_delta': _dec(p.portfolio_delta),
        'portfolio_gamma': _dec(p.portfolio_gamma),
        'portfolio_theta': _dec(p.portfolio_theta),
        'portfolio_vega': _dec(p.portfolio_vega),
        'max_portfolio_delta': _dec(p.max_portfolio_delta) or 500,
        'max_portfolio_gamma': _dec(p.max_portfolio_gamma) or 50,
        'min_portfolio_theta': _dec(p.min_portfolio_theta) or -500,
        'max_portfolio_vega': _dec(p.max_portfolio_vega) or 1000,
        'max_position_size_pct': _dec(p.max_position_size_pct),
        'max_single_trade_risk_pct': _dec(p.max_single_trade_risk_pct),
        'max_total_risk_pct': _dec(p.max_total_risk_pct),
        'var_1d_95': _dec(p.var_1d_95),
        'var_1d_99': _dec(p.var_1d_99),
        'total_pnl': _dec(p.total_pnl),
        'daily_pnl': _dec(p.daily_pnl),
        'realized_pnl': _dec(p.realized_pnl),
        'unrealized_pnl': _dec(p.unrealized_pnl),
        'deployed_pct': round(deployed_pct, 1),
        'open_trade_count': open_count,
    }


def create_v2_router(engine: 'WorkflowEngine') -> APIRouter:
    """Create the v2 API router wired to the workflow engine."""

    router = APIRouter()

    # ------------------------------------------------------------------
    # Portfolios
    # ------------------------------------------------------------------

    @router.get("/portfolios")
    async def get_portfolios():
        """All non-deprecated portfolios with full detail."""
        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type != 'deprecated')
                .order_by(PortfolioORM.name)
                .all()
            )
            # Count open trades per portfolio
            open_counts = dict(
                session.query(
                    TradeORM.portfolio_id,
                    func.count(TradeORM.id),
                )
                .filter(TradeORM.is_open == True)
                .group_by(TradeORM.portfolio_id)
                .all()
            )
            return [
                _serialize_portfolio(p, open_counts.get(p.id, 0))
                for p in portfolios
            ]

    @router.get("/portfolios/{name}")
    async def get_portfolio(name: str):
        """Single portfolio by name."""
        with session_scope() as session:
            p = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.name == name)
                .first()
            )
            if not p:
                raise HTTPException(404, f"Portfolio '{name}' not found")
            open_count = (
                session.query(func.count(TradeORM.id))
                .filter(TradeORM.portfolio_id == p.id, TradeORM.is_open == True)
                .scalar()
            )
            return _serialize_portfolio(p, open_count or 0)

    @router.get("/portfolios/{name}/trades")
    async def get_portfolio_trades(
        name: str,
        status: Optional[str] = Query(None, description="Filter: open, closed, all"),
    ):
        """All trades for a portfolio, with legs."""
        with session_scope() as session:
            p = session.query(PortfolioORM).filter(PortfolioORM.name == name).first()
            if not p:
                raise HTTPException(404, f"Portfolio '{name}' not found")

            q = (
                session.query(TradeORM)
                .filter(TradeORM.portfolio_id == p.id)
                .order_by(TradeORM.created_at.desc())
            )
            if status == 'open':
                q = q.filter(TradeORM.is_open == True)
            elif status == 'closed':
                q = q.filter(TradeORM.is_open == False)
            # else: all

            trades = q.all()
            return [_serialize_trade(t) for t in trades]

    @router.get("/portfolios/{name}/history")
    async def get_portfolio_history(
        name: str,
        days: int = Query(30, description="Number of days of history"),
    ):
        """Daily performance time series for a portfolio."""
        with session_scope() as session:
            p = session.query(PortfolioORM).filter(PortfolioORM.name == name).first()
            if not p:
                raise HTTPException(404, f"Portfolio '{name}' not found")

            from_date = datetime.utcnow() - __import__('datetime').timedelta(days=days)
            snapshots = (
                session.query(DailyPerformanceORM)
                .filter(
                    DailyPerformanceORM.portfolio_id == p.id,
                    DailyPerformanceORM.date >= from_date,
                )
                .order_by(DailyPerformanceORM.date)
                .all()
            )
            return [
                {
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
    # Positions (open trades)
    # ------------------------------------------------------------------

    @router.get("/positions")
    async def get_positions(
        portfolio: Optional[str] = Query(None, description="Filter by portfolio name"),
    ):
        """All open positions (trades) with legs and P&L attribution."""
        with session_scope() as session:
            q = (
                session.query(TradeORM)
                .filter(TradeORM.is_open == True)
                .order_by(TradeORM.underlying_symbol)
            )
            if portfolio:
                p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
                if p:
                    q = q.filter(TradeORM.portfolio_id == p.id)
            trades = q.all()
            return [_serialize_trade(t) for t in trades]

    @router.get("/positions/{trade_id}")
    async def get_position(trade_id: str):
        """Single trade with full detail including legs."""
        with session_scope() as session:
            trade = session.query(TradeORM).filter(TradeORM.id == trade_id).first()
            if not trade:
                raise HTTPException(404, f"Trade '{trade_id}' not found")
            return _serialize_trade(trade)

    # ------------------------------------------------------------------
    # Trades (all, paginated)
    # ------------------------------------------------------------------

    @router.get("/trades")
    async def get_trades(
        portfolio: Optional[str] = Query(None),
        status: Optional[str] = Query(None, description="open, closed, all"),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """All trades, paginated and filterable."""
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

            total = q.count()
            trades = q.offset(offset).limit(limit).all()
            return {
                'total': total,
                'trades': [_serialize_trade(t) for t in trades],
            }

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    @router.get("/recommendations")
    async def get_recommendations(
        status: Optional[str] = Query(None, description="pending, accepted, rejected, all"),
    ):
        """All recommendations."""
        with session_scope() as session:
            q = session.query(RecommendationORM).order_by(RecommendationORM.created_at.desc())
            if status and status != 'all':
                q = q.filter(RecommendationORM.status == status)
            recs = q.limit(200).all()
            return [
                {
                    'id': r.id,
                    'recommendation_type': r.recommendation_type,
                    'source': r.source,
                    'screener_name': r.screener_name,
                    'underlying': r.underlying,
                    'strategy_type': r.strategy_type,
                    'legs': r.legs,
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
            ]

    # ------------------------------------------------------------------
    # Workflow & Agents
    # ------------------------------------------------------------------

    @router.get("/workflow/status")
    async def get_workflow_status():
        """Workflow engine status summary."""
        ctx = engine.context
        macro = ctx.get('macro_assessment', {})

        pending_count = 0
        try:
            with session_scope() as session:
                pending_count = (
                    session.query(func.count(RecommendationORM.id))
                    .filter(RecommendationORM.status == 'pending')
                    .scalar() or 0
                )
        except Exception:
            pass

        return {
            'current_state': engine.state,
            'previous_state': ctx.get('previous_state'),
            'cycle_count': ctx.get('cycle_count', 0),
            'halted': bool(ctx.get('halt_reason')),
            'halt_reason': ctx.get('halt_reason'),
            'last_transition_at': _iso(ctx.get('last_transition_at')),
            'vix': ctx.get('vix'),
            'macro_regime': macro.get('regime'),
            'trades_today': ctx.get('trades_today_count', 0),
            'pending_recommendations': pending_count,
        }

    @router.get("/workflow/agents")
    async def get_workflow_agents():
        """Agent status and metrics."""
        objectives = engine.context.get('session_objectives', {})
        performance = engine.context.get('session_performance', {})

        agents_info = []
        for name in [
            'guardian', 'market_data', 'portfolio_state', 'calendar',
            'macro', 'screener', 'evaluator', 'risk', 'executor',
            'notifier', 'reporter', 'accountability', 'capital_utilization',
            'session_objectives', 'qa',
        ]:
            agents_info.append({
                'name': name,
                'objectives': objectives.get(name, []),
                'performance': performance.get(name, {}),
            })
        return agents_info

    # ------------------------------------------------------------------
    # Risk
    # ------------------------------------------------------------------

    @router.get("/risk")
    async def get_risk():
        """Full risk dashboard data."""
        ctx = engine.context
        risk = ctx.get('risk_snapshot', {})
        macro = ctx.get('macro_assessment', {})
        guardian = ctx.get('guardian_status', {})

        return {
            'var': {
                'var_95': risk.get('var_95'),
                'var_99': risk.get('var_99'),
                'expected_shortfall_95': risk.get('expected_shortfall_95'),
            },
            'macro': {
                'regime': macro.get('regime'),
                'vix': ctx.get('vix'),
                'confidence': macro.get('confidence'),
                'rationale': macro.get('rationale', '')[:200],
            },
            'circuit_breakers': guardian.get('circuit_breakers', {}),
            'trading_constraints': {
                'trades_today': ctx.get('trades_today_count', 0),
                'max_trades_per_day': 3,
                'halted': bool(ctx.get('halt_reason')),
                'halt_reason': ctx.get('halt_reason'),
            },
        }

    # ------------------------------------------------------------------
    # Capital
    # ------------------------------------------------------------------

    @router.get("/capital")
    async def get_capital():
        """Capital utilization with severity alerts."""
        ctx_capital = engine.context.get('capital_utilization', {})
        ctx_portfolios = ctx_capital.get('portfolios', {})

        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type.in_(['real', 'paper']))
                .order_by(PortfolioORM.name)
                .all()
            )
            result = []
            for p in portfolios:
                equity = _dec(p.total_equity)
                cash = _dec(p.cash_balance)
                deployed_pct = ((equity - cash) / equity * 100) if equity else 0
                pdata = ctx_portfolios.get(p.name, {})
                result.append({
                    'name': p.name,
                    'initial_capital': _dec(p.initial_capital),
                    'total_equity': equity,
                    'cash_balance': cash,
                    'deployed_pct': round(deployed_pct, 1),
                    'idle_capital': cash,
                    'severity': pdata.get('severity', 'ok'),
                    'opp_cost_daily': float(pdata['opp_cost_daily']) if pdata.get('opp_cost_daily') is not None else None,
                })
            return result

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    @router.get("/decisions")
    async def get_decisions(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """Decision log entries, paginated."""
        with session_scope() as session:
            q = (
                session.query(DecisionLogORM)
                .order_by(DecisionLogORM.presented_at.desc())
            )
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
                        'time_to_decision_seconds': d.time_to_decision_seconds,
                    }
                    for d in entries
                ],
            }

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    @router.get("/performance")
    async def get_performance():
        """Portfolio performance metrics."""
        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type != 'deprecated')
                .order_by(PortfolioORM.name)
                .all()
            )
            result = []
            for p in portfolios:
                # Count trades
                total_trades = (
                    session.query(func.count(TradeORM.id))
                    .filter(TradeORM.portfolio_id == p.id)
                    .scalar() or 0
                )
                open_trades = (
                    session.query(func.count(TradeORM.id))
                    .filter(TradeORM.portfolio_id == p.id, TradeORM.is_open == True)
                    .scalar() or 0
                )
                closed_trades = total_trades - open_trades

                # Win rate
                winning = (
                    session.query(func.count(TradeORM.id))
                    .filter(
                        TradeORM.portfolio_id == p.id,
                        TradeORM.is_open == False,
                        TradeORM.total_pnl > 0,
                    )
                    .scalar() or 0
                )
                win_rate = (winning / closed_trades * 100) if closed_trades else 0

                result.append({
                    'name': p.name,
                    'portfolio_type': p.portfolio_type,
                    'total_pnl': _dec(p.total_pnl),
                    'daily_pnl': _dec(p.daily_pnl),
                    'realized_pnl': _dec(p.realized_pnl),
                    'unrealized_pnl': _dec(p.unrealized_pnl),
                    'total_trades': total_trades,
                    'open_trades': open_trades,
                    'closed_trades': closed_trades,
                    'win_rate': round(win_rate, 1),
                })
            return result

    return router
