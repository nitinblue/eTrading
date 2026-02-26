"""
v2 API Router — Comprehensive endpoints for the React frontend.

Mounted in approval_api.py at /api/v2 prefix.
Existing /api/* endpoints remain unchanged.
"""

from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
import asyncio
import logging

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import (
    PortfolioORM,
    PositionORM,
    TradeORM,
    LegORM,
    StrategyORM,
    SymbolORM,
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


def _get_margin_buffer_multiplier() -> float:
    """Load margin_buffer_multiplier from risk_config.yaml."""
    try:
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "risk_config.yaml"
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        return float(cfg.get('margin', {}).get('margin_buffer_multiplier', 2.0))
    except Exception:
        return 2.0


def _serialize_portfolio(p: PortfolioORM, open_count: int = 0) -> dict:
    """Serialize a portfolio ORM."""
    equity = _dec(p.total_equity)
    cash = _dec(p.cash_balance)
    initial = _dec(p.initial_capital)
    buying_power = _dec(p.buying_power)
    deployed_pct = ((equity - cash) / equity * 100) if equity else 0

    # Margin computations
    margin_used = max(equity - buying_power, 0) if equity else 0
    available_margin = buying_power
    buffer_mult = _get_margin_buffer_multiplier()
    margin_buffer = margin_used * buffer_mult
    margin_utilization_pct = (margin_used / equity * 100) if equity else 0
    margin_buffer_remaining = available_margin - margin_buffer
    risk_pct_of_margin = ((_dec(p.var_1d_95) / margin_used) * 100) if margin_used else 0

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
        'buying_power': buying_power,
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
        # Margin / Capital columns
        'margin_used': round(margin_used, 2),
        'available_margin': round(available_margin, 2),
        'margin_utilization_pct': round(margin_utilization_pct, 1),
        'margin_buffer': round(margin_buffer, 2),
        'margin_buffer_remaining': round(margin_buffer_remaining, 2),
        'risk_pct_of_margin': round(risk_pct_of_margin, 1),
        'margin_buffer_multiplier': buffer_mult,
    }


def _load_positions_from_db(portfolio: Optional[str] = None) -> dict:
    """Load broker positions from DB when containers not initialized."""
    from trading_cotrader.containers.position_container import PositionContainer

    try:
        with session_scope() as session:
            q = session.query(PositionORM)
            if portfolio:
                p = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio).first()
                if p:
                    q = q.filter(PositionORM.portfolio_id == p.id)
            positions = q.all()
            temp = PositionContainer()
            temp.load_from_orm_list(positions)
            return {'positions': temp.to_grid_rows(), 'count': temp.count}
    except Exception as e:
        logger.warning(f"Failed to load positions from DB: {e}")
        return {'positions': [], 'count': 0}


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
    # Workflow & Agents
    # ------------------------------------------------------------------

    @router.get("/workflow/status")
    async def get_workflow_status():
        """Workflow engine status summary."""
        ctx = engine.context
        macro = ctx.get('macro_assessment', {})

        pending_count = 0

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

    # ------------------------------------------------------------------
    # Risk Factors (per-underlying risk aggregation from containers)
    # ------------------------------------------------------------------

    @router.get("/risk/factors")
    async def get_risk_factors(
        portfolio: Optional[str] = Query(None, description="Filter by portfolio name"),
    ):
        """Per-underlying risk factor aggregation for delta-neutral monitoring."""
        if engine and engine.container_manager:
            cm = engine.container_manager
            if portfolio:
                bundle = cm.get_bundle(portfolio)
                if bundle and bundle.risk_factors.is_initialized:
                    rows = bundle.risk_factors.to_grid_rows()
                    for r in rows:
                        r['account'] = bundle.config_name
                    return {'factors': rows}
                return {'factors': []}
            # All risk factors from all bundles
            all_factors = []
            for bundle in cm.get_all_bundles():
                if bundle.risk_factors.is_initialized:
                    rows = bundle.risk_factors.to_grid_rows()
                    for r in rows:
                        r['account'] = bundle.config_name
                    all_factors.extend(rows)
            if all_factors:
                return {'factors': all_factors}
            # Fallback to default bundle
            if cm.risk_factors.is_initialized:
                return {'factors': cm.risk_factors.to_grid_rows()}
        return {'factors': []}

    @router.get("/risk/factors/{underlying}")
    async def get_risk_factor(underlying: str):
        """Risk factor detail for a single underlying."""
        if engine and engine.container_manager:
            cm = engine.container_manager
            # Search across all bundles
            for bundle in cm.get_all_bundles():
                rf = bundle.risk_factors.get(underlying.upper())
                if rf:
                    return rf.to_dict()
            # Fallback to default
            rf = cm.risk_factors.get(underlying.upper())
            if rf:
                return rf.to_dict()
        raise HTTPException(status_code=404, detail=f"No risk factor for {underlying}")

    # ------------------------------------------------------------------
    # Broker Positions (synced from broker, container-backed)
    # ------------------------------------------------------------------

    @router.get("/broker-positions")
    async def get_broker_positions(
        portfolio: Optional[str] = Query(None, description="Filter by portfolio name"),
    ):
        """Broker-synced positions from PositionContainer."""
        if engine and engine.container_manager:
            cm = engine.container_manager
            if portfolio:
                bundle = cm.get_bundle(portfolio)
                if bundle and bundle.positions.is_initialized:
                    rows = bundle.positions.to_grid_rows()
                    for r in rows:
                        r['account'] = bundle.config_name
                    return {
                        'positions': rows,
                        'count': bundle.positions.count,
                    }
            else:
                # All positions from all bundles
                all_positions = []
                for bundle in cm.get_all_bundles():
                    if bundle.positions.is_initialized:
                        rows = bundle.positions.to_grid_rows()
                        for r in rows:
                            r['account'] = bundle.config_name
                        all_positions.extend(rows)
                if all_positions:
                    return {'positions': all_positions, 'count': len(all_positions)}
                # Fallback to default bundle
                if cm.positions.is_initialized:
                    return {
                        'positions': cm.positions.to_grid_rows(),
                        'count': cm.positions.count,
                    }
        # Fallback: load from DB directly when containers aren't initialized
        return _load_positions_from_db(portfolio)

    # ------------------------------------------------------------------
    # Market Data (technical indicators from MarketDataContainer)
    # ------------------------------------------------------------------

    @router.get("/market-data")
    async def get_market_data():
        """All tracked underlyings with technical indicators."""
        if engine and hasattr(engine, 'container_manager'):
            cm = engine.container_manager
            if cm and hasattr(cm, 'market_data'):
                return {
                    'symbols': cm.market_data.symbols,
                    'count': cm.market_data.count,
                    'data': cm.market_data.to_grid_rows(),
                }
        return {'symbols': [], 'count': 0, 'data': []}

    @router.get("/market-data/{symbol}")
    async def get_market_data_symbol(symbol: str):
        """Technical indicators for a single underlying."""
        if engine and hasattr(engine, 'container_manager'):
            cm = engine.container_manager
            if cm and hasattr(cm, 'market_data'):
                entry = cm.market_data.get(symbol.upper())
                if entry:
                    return entry.to_dict()
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}")

    # ------------------------------------------------------------------
    # Agent Intelligence (LLM-powered analysis)
    # ------------------------------------------------------------------

    @router.get("/agent/brief")
    async def get_agent_brief():
        """Get intelligent portfolio brief from the agent brain."""
        from trading_cotrader.services.agent_brain import get_agent_brain

        brain = get_agent_brain()
        if not brain.is_available:
            return {
                'available': False,
                'brief': '[Agent brain not configured. Add ANTHROPIC_API_KEY to .env]',
            }

        # Gather all available data for the agent
        positions = []
        balances = {}
        transactions = []
        market_metrics = {}
        pending_recs = []
        capital_alerts = []

        try:
            # Get positions from broker
            if engine and hasattr(engine, '_adapters'):
                for name, adapter in engine._adapters.items():
                    try:
                        bal = adapter.get_account_balance()
                        if bal:
                            balances[name] = {k: float(v) for k, v in bal.items()}
                        pos_list = adapter.get_positions()
                        for p in pos_list:
                            positions.append({
                                'symbol': p.symbol.ticker,
                                'type': str(p.symbol.asset_type.value) if p.symbol.asset_type else 'equity',
                                'quantity': int(p.quantity),
                                'entry_price': float(p.entry_price),
                                'current_price': float(p.current_price),
                                'market_value': float(p.market_value),
                                'pnl': float(p.current_price - p.entry_price) * int(p.quantity) * int(p.symbol.multiplier),
                                'delta': float(p.greeks.delta) if p.greeks else 0,
                                'theta': float(p.greeks.theta) if p.greeks else 0,
                                'gamma': float(p.greeks.gamma) if p.greeks else 0,
                                'vega': float(p.greeks.vega) if p.greeks else 0,
                                'strike': float(p.symbol.strike) if p.symbol.strike else None,
                                'expiration': p.symbol.expiration.strftime('%Y-%m-%d') if p.symbol.expiration else None,
                                'option_type': p.symbol.option_type.value if p.symbol.option_type else None,
                            })
                        # Get recent transactions
                        if hasattr(adapter, 'get_transaction_history'):
                            try:
                                seven_days_ago = date_cls.today() - __import__('datetime').timedelta(days=7)
                                transactions = adapter.get_transaction_history(start_date=seven_days_ago)
                            except Exception:
                                pass
                        # Get market metrics for position underlyings
                        if hasattr(adapter, 'get_market_metrics'):
                            try:
                                underlyings = list(set(p['symbol'] for p in positions if p.get('type') != 'option'))
                                option_underlyings = list(set(
                                    p['symbol'] for p in positions if p.get('type') == 'option'
                                ))
                                all_symbols = list(set(underlyings + option_underlyings))
                                if all_symbols:
                                    market_metrics = adapter.get_market_metrics(all_symbols[:20])
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(f"Failed to get data from {name}: {e}")


            # Get capital alerts from engine context
            if engine and hasattr(engine, 'context'):
                capital_alerts = engine.context.get('capital_alerts', [])

        except Exception as e:
            logger.error(f"Error gathering data for agent brief: {e}")

        # Generate the brief
        brief = brain.generate_portfolio_brief(
            positions=positions,
            balances=balances,
            transactions=transactions,
            market_metrics=market_metrics,
            pending_recommendations=pending_recs,
            capital_alerts=capital_alerts,
        )

        return {
            'available': True,
            'brief': brief,
            'generated_at': datetime.now().isoformat(),
            'data_summary': {
                'positions': len(positions),
                'transactions': len(transactions),
                'pending_recs': len(pending_recs),
                'has_market_metrics': bool(market_metrics),
            },
        }

    @router.post("/agent/chat")
    async def agent_chat(body: dict):
        """Chat with the agent brain."""
        from trading_cotrader.services.agent_brain import get_agent_brain

        brain = get_agent_brain()
        if not brain.is_available:
            return {
                'available': False,
                'response': '[Agent brain not configured. Add ANTHROPIC_API_KEY to .env]',
            }

        message = body.get('message', '')
        if not message:
            raise HTTPException(400, "Message is required")

        # Build portfolio context for the chat
        context = {}
        try:
            if engine and hasattr(engine, '_adapters'):
                for name, adapter in engine._adapters.items():
                    try:
                        bal = adapter.get_account_balance()
                        if bal:
                            context['balances'] = {k: float(v) for k, v in bal.items()}
                        pos_list = adapter.get_positions()
                        context['positions'] = [
                            {
                                'symbol': p.symbol.ticker,
                                'quantity': int(p.quantity),
                                'delta': float(p.greeks.delta) if p.greeks else 0,
                                'theta': float(p.greeks.theta) if p.greeks else 0,
                            }
                            for p in pos_list
                        ]
                    except Exception:
                        pass
        except Exception:
            pass

        response = brain.chat_response(message, portfolio_context=context or None)

        return {
            'available': True,
            'response': response,
            'generated_at': datetime.now().isoformat(),
        }

    @router.get("/agent/analyze/{symbol}")
    async def agent_analyze_position(symbol: str):
        """Get agent analysis of a specific position."""
        from trading_cotrader.services.agent_brain import get_agent_brain

        brain = get_agent_brain()
        if not brain.is_available:
            return {'available': False, 'analysis': '[Agent brain not configured]'}

        # Find the position
        position_data = None
        market_data = None
        tx_history = []

        try:
            if engine and hasattr(engine, '_adapters'):
                for name, adapter in engine._adapters.items():
                    try:
                        pos_list = adapter.get_positions()
                        for p in pos_list:
                            if p.symbol.ticker.upper() == symbol.upper():
                                position_data = {
                                    'symbol': p.symbol.ticker,
                                    'type': str(p.symbol.asset_type.value),
                                    'quantity': int(p.quantity),
                                    'entry_price': float(p.entry_price),
                                    'current_price': float(p.current_price),
                                    'market_value': float(p.market_value),
                                    'delta': float(p.greeks.delta) if p.greeks else 0,
                                    'theta': float(p.greeks.theta) if p.greeks else 0,
                                    'gamma': float(p.greeks.gamma) if p.greeks else 0,
                                    'vega': float(p.greeks.vega) if p.greeks else 0,
                                    'strike': float(p.symbol.strike) if p.symbol.strike else None,
                                    'expiration': p.symbol.expiration.strftime('%Y-%m-%d') if p.symbol.expiration else None,
                                    'option_type': p.symbol.option_type.value if p.symbol.option_type else None,
                                }
                                break
                        # Get market metrics
                        if hasattr(adapter, 'get_market_metrics'):
                            try:
                                metrics = adapter.get_market_metrics([symbol.upper()])
                                market_data = metrics.get(symbol.upper())
                            except Exception:
                                pass
                        # Get transaction history for this symbol
                        if hasattr(adapter, 'get_transaction_history'):
                            try:
                                tx_history = adapter.get_transaction_history(
                                    underlying_symbol=symbol.upper()
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error getting position data: {e}")

        if not position_data:
            raise HTTPException(404, f"Position {symbol} not found")

        analysis = brain.analyze_position(
            position=position_data,
            market_data=market_data,
            transaction_history=tx_history,
        )

        return {
            'available': True,
            'analysis': analysis,
            'position': position_data,
            'generated_at': datetime.now().isoformat(),
        }

    @router.get("/agent/status")
    async def agent_status():
        """Check if the agent brain is available and what it can do."""
        from trading_cotrader.services.agent_brain import get_agent_brain

        brain = get_agent_brain()
        has_adapters = bool(engine and hasattr(engine, '_adapters') and engine._adapters)

        return {
            'llm_available': brain.is_available,
            'broker_connected': has_adapters,
            'capabilities': {
                'portfolio_brief': brain.is_available and has_adapters,
                'position_analysis': brain.is_available and has_adapters,
                'chat': brain.is_available,
                'recommendations': brain.is_available,
                'accountability': brain.is_available,
            },
        }

    # ------------------------------------------------------------------
    # Account Activity (transaction history from broker)
    # ------------------------------------------------------------------

    @router.get("/account/transactions")
    async def get_transactions(
        days: int = Query(7, description="Number of days of history"),
        underlying: Optional[str] = Query(None, description="Filter by underlying symbol"),
    ):
        """Get transaction history from connected brokers."""
        results = []
        if engine and hasattr(engine, '_adapters'):
            start = date_cls.today() - __import__('datetime').timedelta(days=days)
            for name, adapter in engine._adapters.items():
                if hasattr(adapter, 'get_transaction_history'):
                    try:
                        txs = adapter.get_transaction_history(
                            start_date=start,
                            underlying_symbol=underlying,
                        )
                        for t in txs:
                            t['broker'] = name
                        results.extend(txs)
                    except Exception as e:
                        logger.warning(f"Failed to get transactions from {name}: {e}")
        return {'transactions': results, 'count': len(results)}

    @router.get("/account/orders")
    async def get_order_history(
        days: int = Query(7, description="Number of days of history"),
        underlying: Optional[str] = Query(None, description="Filter by underlying"),
    ):
        """Get order history from connected brokers."""
        results = []
        if engine and hasattr(engine, '_adapters'):
            start = date_cls.today() - __import__('datetime').timedelta(days=days)
            for name, adapter in engine._adapters.items():
                if hasattr(adapter, 'get_order_history'):
                    try:
                        orders = adapter.get_order_history(
                            start_date=start,
                            underlying_symbol=underlying,
                        )
                        for o in orders:
                            o['broker'] = name
                        results.extend(orders)
                    except Exception as e:
                        logger.warning(f"Failed to get order history from {name}: {e}")
        return {'orders': results, 'count': len(results)}

    @router.get("/account/live-orders")
    async def get_live_orders():
        """Get all working/pending orders from connected brokers."""
        results = []
        if engine and hasattr(engine, '_adapters'):
            for name, adapter in engine._adapters.items():
                if hasattr(adapter, 'get_live_orders'):
                    try:
                        orders = adapter.get_live_orders()
                        for o in orders:
                            o['broker'] = name
                        results.extend(orders)
                    except Exception as e:
                        logger.warning(f"Failed to get live orders from {name}: {e}")
        return {'orders': results, 'count': len(results)}

    @router.get("/account/equity-curve")
    async def get_equity_curve(
        period: str = Query('1m', description="Time period: 1d, 1m, 3m, 6m, 1y, all"),
    ):
        """Get net liquidating value history for equity curve chart."""
        results = []
        if engine and hasattr(engine, '_adapters'):
            for name, adapter in engine._adapters.items():
                if hasattr(adapter, 'get_net_liq_history'):
                    try:
                        data = adapter.get_net_liq_history(time_back=period)
                        return {'broker': name, 'data': data, 'count': len(data)}
                    except Exception as e:
                        logger.warning(f"Failed to get equity curve from {name}: {e}")
        return {'data': [], 'count': 0}

    @router.get("/account/market-metrics")
    async def get_broker_market_metrics(
        symbols: str = Query(..., description="Comma-separated symbols"),
    ):
        """Get IV rank, IV percentile, beta from broker."""
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
        if engine and hasattr(engine, '_adapters'):
            for name, adapter in engine._adapters.items():
                if hasattr(adapter, 'get_market_metrics'):
                    try:
                        metrics = adapter.get_market_metrics(symbol_list)
                        return {'broker': name, 'metrics': metrics}
                    except Exception as e:
                        logger.warning(f"Failed to get market metrics from {name}: {e}")
        return {'metrics': {}}

    # ------------------------------------------------------------------
    # MarketAnalyzer facade (lazy singleton — exposes regime, technicals,
    # phase, opportunity, fundamentals, macro services)
    # ------------------------------------------------------------------

    _ma_holder: dict = {}

    def _get_market_analyzer():
        """Get or create MarketAnalyzer facade singleton."""
        if 'ma' not in _ma_holder:
            from market_analyzer import MarketAnalyzer
            from market_analyzer.data import DataService
            _ma_holder['ma'] = MarketAnalyzer(data_service=DataService())
        return _ma_holder['ma']

    # ------------------------------------------------------------------
    # Market Watchlist (configurable watchlist + regime detection)
    # ------------------------------------------------------------------

    @router.get("/market/watchlist")
    async def get_market_watchlist():
        """
        Return configured market watchlist with current HMM regime for each ticker.

        First checks ResearchContainer for cached regime data.
        Falls back to library calls only for tickers missing from container.
        """
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent.parent / 'config' / 'market_watchlist.yaml'
        if not config_path.exists():
            raise HTTPException(404, "market_watchlist.yaml not found")

        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)

        items = cfg.get('watchlist', [])
        if not items:
            return []

        tickers = [item['ticker'] for item in items]

        # Try to read regime data from ResearchContainer first
        container_map = {}
        cm = engine.container_manager if engine else None
        if cm is not None:
            research = cm.research
            for t in tickers:
                entry = research.get(t)
                if entry and entry.hmm_regime_id is not None:
                    container_map[t] = {
                        'regime': entry.hmm_regime_id,
                        'regime_name': entry.hmm_regime_label or 'UNKNOWN',
                        'confidence': entry.hmm_confidence or 0,
                        'trend_direction': entry.hmm_trend_direction,
                        'strategy_comment': entry.hmm_strategy_comment or '',
                    }

        # Fall back to library for tickers missing from container
        missing_tickers = [t for t in tickers if t not in container_map]
        regime_map = {}
        strategy_map = {}

        if missing_tickers:
            try:
                ma = _get_market_analyzer()
                results = await asyncio.to_thread(ma.regime.detect_batch, tickers=missing_tickers)
                for ticker_key, r in results.items():
                    regime_map[ticker_key] = {
                        'regime': r.regime.value,
                        'regime_name': r.regime.name,
                        'confidence': r.confidence,
                        'trend_direction': r.trend_direction,
                    }
            except Exception as e:
                logger.warning(f"Regime batch detection failed for watchlist: {e}")

            # Strategy comments for missing tickers
            try:
                ma = _get_market_analyzer()
                for t in missing_tickers:
                    try:
                        research = await asyncio.to_thread(ma.regime.research, t)
                        strategy_map[t] = research.strategy_comment
                    except Exception:
                        strategy_map[t] = ''
            except Exception:
                pass

        result = []
        for item in items:
            t = item['ticker']
            # Prefer container data, fall back to library
            if t in container_map:
                info = container_map[t]
                result.append({
                    'name': item['name'],
                    'ticker': t,
                    'asset_class': item.get('asset_class', ''),
                    'regime': info['regime'],
                    'regime_name': info['regime_name'],
                    'confidence': info['confidence'],
                    'trend_direction': info['trend_direction'],
                    'strategy_comment': info.get('strategy_comment', ''),
                })
            else:
                regime_info = regime_map.get(t, {})
                result.append({
                    'name': item['name'],
                    'ticker': t,
                    'asset_class': item.get('asset_class', ''),
                    'regime': regime_info.get('regime', 0),
                    'regime_name': regime_info.get('regime_name', 'UNKNOWN'),
                    'confidence': regime_info.get('confidence', 0),
                    'trend_direction': regime_info.get('trend_direction'),
                    'strategy_comment': strategy_map.get(t, ''),
                })

        return result

    # ------------------------------------------------------------------
    # Market Regime (HMM-based regime detection via market_analyzer library)
    # ------------------------------------------------------------------

    @router.get("/regime/{ticker}")
    async def get_regime(ticker: str):
        """
        Tier 1: Get current regime label for a single ticker.

        Returns regime ID (R1-R4), confidence, trend direction,
        and probability distribution across all regimes.
        """
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.regime.detect, ticker.upper())
            return {
                'ticker': result.ticker,
                'regime': result.regime.value,
                'regime_name': result.regime.name,
                'confidence': result.confidence,
                'trend_direction': result.trend_direction,
                'regime_probabilities': {
                    str(k): v for k, v in result.regime_probabilities.items()
                },
                'as_of_date': result.as_of_date.isoformat() if result.as_of_date else None,
                'model_version': result.model_version,
            }
        except Exception as e:
            logger.error(f"Regime detection failed for {ticker}: {e}")
            raise HTTPException(500, f"Regime detection failed: {e}")

    @router.post("/regime/batch")
    async def get_regime_batch(body: dict):
        """
        Tier 1 batch: Get regime labels for multiple tickers.

        Request body: {"tickers": ["SPY", "QQQ", "GLD", "TLT"]}
        """
        tickers = body.get('tickers', [])
        if not tickers:
            raise HTTPException(400, "tickers list is required")

        try:
            ma = _get_market_analyzer()
            results = await asyncio.to_thread(ma.regime.detect_batch, tickers=[t.upper() for t in tickers])
            return {
                'results': {
                    ticker: {
                        'regime': r.regime.value,
                        'regime_name': r.regime.name,
                        'confidence': r.confidence,
                        'trend_direction': r.trend_direction,
                        'regime_probabilities': {
                            str(k): v for k, v in r.regime_probabilities.items()
                        },
                        'as_of_date': r.as_of_date.isoformat() if r.as_of_date else None,
                    }
                    for ticker, r in results.items()
                },
                'count': len(results),
            }
        except Exception as e:
            logger.error(f"Batch regime detection failed: {e}")
            raise HTTPException(500, f"Batch regime detection failed: {e}")

    @router.get("/regime/{ticker}/research")
    async def get_regime_research(ticker: str):
        """
        Tier 2: Full research for a single ticker.

        Returns regime + transition matrix, state means, feature z-scores,
        recent history (20 days), regime distribution, strategy comment.
        """
        try:
            ma = _get_market_analyzer()
            r = await asyncio.to_thread(ma.regime.research, ticker.upper())
            return r.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Regime research failed for {ticker}: {e}")
            raise HTTPException(500, f"Regime research failed: {e}")

    @router.get("/regime/{ticker}/chart")
    async def get_regime_chart(ticker: str):
        """
        Return regime detection chart as PNG image.

        Uses market_analyzer plot_ticker() to generate a two-panel chart:
        top = price with colored regime bands, bottom = confidence bars.
        """
        import io
        import base64
        try:
            ma = _get_market_analyzer()
            explanation = await asyncio.to_thread(ma.regime.explain, ticker.upper())
            ohlcv = await asyncio.to_thread(ma.data.get_ohlcv, ticker.upper())

            # Generate chart to BytesIO
            from market_analyzer.cli.plot import plot_ticker as _plot_ticker
            import matplotlib
            matplotlib.use('Agg')  # non-interactive backend
            import matplotlib.pyplot as _plt

            # Temporarily monkey-patch to capture bytes
            buf = io.BytesIO()

            # Replicate plot_ticker but save to buffer
            from market_analyzer.config import get_settings as _get_settings
            from market_analyzer.models.regime import RegimeID as _RegimeID
            import matplotlib.dates as _mdates
            import numpy as _np

            settings = _get_settings()
            plot_cfg = settings.display.plot
            regime_colors = {_RegimeID(k): v for k, v in settings.regimes.colors.items()}
            regime_labels = {_RegimeID(k): v for k, v in settings.regimes.labels.items()}

            entries = explanation.regime_series.entries
            if not entries:
                raise HTTPException(404, f"No regime series for {ticker}")

            dates = [e.date for e in entries]
            regimes = [e.regime for e in entries]
            confidences = [e.confidence for e in entries]

            ohlcv_copy = ohlcv.copy()
            ohlcv_copy.index = ohlcv_copy.index.date
            prices = [
                ohlcv_copy.loc[d, "Close"] if d in ohlcv_copy.index else _np.nan
                for d in dates
            ]

            transitions = []
            for i in range(1, len(regimes)):
                if regimes[i] != regimes[i - 1]:
                    transitions.append(i)

            fig, (ax_price, ax_conf) = _plt.subplots(
                2, 1,
                figsize=tuple(plot_cfg.figure_size),
                sharex=True,
                gridspec_kw={
                    "hspace": 0.05,
                    "height_ratios": list(plot_cfg.height_ratios)[:2] if plot_cfg.height_ratios else [3, 1],
                },
            )

            ax_price.plot(dates, prices, color="black", linewidth=0.8, zorder=3)

            i = 0
            while i < len(dates):
                j = i + 1
                while j < len(dates) and regimes[j] == regimes[i]:
                    j += 1
                color = regime_colors[regimes[i]]
                ax_price.axvspan(
                    dates[i], dates[min(j, len(dates) - 1)],
                    alpha=0.15, color=color, zorder=1,
                )
                i = j

            for idx in transitions:
                d = dates[idx]
                ax_price.axvline(d, color="gray", linestyle="--", linewidth=0.7, alpha=0.7, zorder=2)
                ax_conf.axvline(d, color="gray", linestyle="--", linewidth=0.7, alpha=0.7, zorder=2)
                if not _np.isnan(prices[idx]):
                    ax_price.plot(
                        d, prices[idx], marker="v",
                        color=regime_colors[regimes[idx]], markersize=6, zorder=4,
                    )

            ax_price.set_ylabel("Close Price")
            ax_price.set_title(f"{ticker.upper()} — Regime Detection", fontsize=13, fontweight="bold")
            ax_price.tick_params(axis="x", labelbottom=False)

            legend_handles = [
                _plt.Line2D([0], [0], color=c, linewidth=6, alpha=0.4, label=regime_labels[rid])
                for rid, c in regime_colors.items()
            ]
            ax_price.legend(
                handles=legend_handles, loc="upper left",
                fontsize=plot_cfg.font_size, framealpha=plot_cfg.legend_alpha,
            )

            bar_colors = [regime_colors[r] for r in regimes]
            ax_conf.bar(dates, confidences, color=bar_colors, width=1.0, alpha=0.7)
            ax_conf.set_ylabel("Confidence")
            ax_conf.set_ylim(0, 1)
            ax_conf.yaxis.set_major_formatter(_plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
            ax_conf.xaxis.set_major_locator(_mdates.MonthLocator(interval=plot_cfg.month_interval))
            ax_conf.xaxis.set_major_formatter(_mdates.DateFormatter("%Y-%m"))
            fig.autofmt_xdate(rotation=plot_cfg.xaxis_rotation)

            _plt.tight_layout()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            _plt.close(fig)
            buf.seek(0)

            png_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return {
                'ticker': ticker.upper(),
                'chart_base64': png_b64,
                'format': 'png',
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Regime chart generation failed for {ticker}: {e}")
            raise HTTPException(500, f"Chart generation failed: {e}")

    @router.post("/regime/research")
    async def get_regime_research_batch(body: dict):
        """
        Tier 2 batch: Full research for multiple tickers with cross-comparison.

        Request body: {"tickers": ["SPY", "QQQ", "GLD"]}
        """
        tickers = body.get('tickers', [])
        if not tickers:
            raise HTTPException(400, "tickers list is required")

        try:
            ma = _get_market_analyzer()
            report = await asyncio.to_thread(ma.regime.research_batch, tickers=[t.upper() for t in tickers])
            return report.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Batch regime research failed: {e}")
            raise HTTPException(500, f"Batch regime research failed: {e}")

    # ------------------------------------------------------------------
    # Technicals (via market_analyzer library)
    # ------------------------------------------------------------------

    @router.get("/technicals/{ticker}")
    async def get_technicals(ticker: str):
        """
        Technical indicators for a single ticker.

        Returns moving averages, RSI, Bollinger, MACD, Stochastic,
        support/resistance, and actionable signals.
        """
        try:
            ma = _get_market_analyzer()
            snapshot = await asyncio.to_thread(ma.technicals.snapshot, ticker.upper())
            return snapshot.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Technicals failed for {ticker}: {e}")
            raise HTTPException(500, f"Technicals failed: {e}")

    # ------------------------------------------------------------------
    # Fundamentals (via market_analyzer library)
    # ------------------------------------------------------------------

    @router.get("/fundamentals/{ticker}")
    async def get_fundamentals(ticker: str):
        """Stock fundamentals: valuation, earnings, margins, cash, debt, dividends, 52w range."""
        try:
            ma = _get_market_analyzer()
            snapshot = await asyncio.to_thread(ma.fundamentals.get, ticker.upper())
            return snapshot.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Fundamentals failed for {ticker}: {e}")
            raise HTTPException(500, f"Fundamentals failed: {e}")

    # ------------------------------------------------------------------
    # Macro Calendar (via market_analyzer library)
    # ------------------------------------------------------------------

    @router.get("/macro/calendar")
    async def get_macro_calendar(lookahead_days: int = 90):
        """Macro economic calendar: FOMC, CPI, NFP, PCE, GDP events."""
        try:
            ma = _get_market_analyzer()
            cal = await asyncio.to_thread(ma.macro.calendar, lookahead_days=lookahead_days)
            return cal.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Macro calendar failed: {e}")
            raise HTTPException(500, f"Macro calendar failed: {e}")

    # ------------------------------------------------------------------
    # Levels Analysis (support/resistance, stop loss, targets)
    # ------------------------------------------------------------------

    @router.get("/levels/{ticker}")
    async def get_levels(
        ticker: str,
        direction: Optional[str] = Query(None, description="Override auto-detected direction: long or short"),
        entry_price: Optional[float] = Query(None, description="Override entry price"),
    ):
        """
        Synthesized price levels: ranked S/R with confluence, stop loss, targets, R:R.

        Uses LevelsService which combines swing S/R, MAs, Bollinger, VCP pivot,
        order blocks, FVGs, ORB, and VWAP into actionable levels.
        """
        try:
            ma = _get_market_analyzer()
            kwargs = {}
            if direction:
                kwargs['direction'] = direction
            if entry_price is not None:
                kwargs['entry_price'] = entry_price
            result = await asyncio.to_thread(ma.levels.analyze, ticker.upper(), **kwargs)
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Levels analysis failed for {ticker}: {e}")
            raise HTTPException(500, f"Levels analysis failed: {e}")

    # ------------------------------------------------------------------
    # Phase Detection (Wyckoff via market_analyzer PhaseService)
    # ------------------------------------------------------------------

    @router.get("/phase/{ticker}")
    async def get_phase(ticker: str):
        """Wyckoff phase detection: accumulation/markup/distribution/markdown."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.phase.detect, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Phase detection failed for {ticker}: {e}")
            raise HTTPException(500, f"Phase detection failed: {e}")

    # ------------------------------------------------------------------
    # Opportunity Assessments (via market_analyzer OpportunityService)
    # ------------------------------------------------------------------

    @router.get("/opportunity/zero-dte/{ticker}")
    async def get_opportunity_zero_dte(ticker: str):
        """0DTE opportunity assessment: verdict, strategy, signals."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_zero_dte, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"0DTE opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"0DTE opportunity assessment failed: {e}")

    @router.get("/opportunity/leap/{ticker}")
    async def get_opportunity_leap(ticker: str):
        """LEAP opportunity assessment: verdict, strategy, fundamental score."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_leap, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"LEAP opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"LEAP opportunity assessment failed: {e}")

    @router.get("/opportunity/breakout/{ticker}")
    async def get_opportunity_breakout(ticker: str):
        """Breakout opportunity assessment: VCP, squeeze, pivot."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_breakout, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Breakout opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Breakout opportunity assessment failed: {e}")

    @router.get("/opportunity/momentum/{ticker}")
    async def get_opportunity_momentum(ticker: str):
        """Momentum opportunity assessment: trend continuation, pullback."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_momentum, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Momentum opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Momentum opportunity assessment failed: {e}")

    # ------------------------------------------------------------------
    # Trade Ranking (via market_analyzer RankingService)
    # ------------------------------------------------------------------

    class RankingRequest(BaseModel):
        tickers: list[str] | None = None

    @router.post("/ranking")
    async def get_ranking(body: RankingRequest | None = None):
        """Rank watchlist tickers across 4 strategy types (0DTE, LEAP, breakout, momentum)."""
        try:
            ma = _get_market_analyzer()
            tickers = body.tickers if body and body.tickers else None
            if not tickers:
                from market_analyzer.config import get_settings
                tickers = get_settings().display.default_tickers
            result = await asyncio.to_thread(ma.ranking.rank, tickers)
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Ranking failed: {e}")
            raise HTTPException(500, f"Ranking failed: {e}")

    # ------------------------------------------------------------------
    # Black Swan / Tail-Risk Alert (via market_analyzer BlackSwanService)
    # ------------------------------------------------------------------

    @router.get("/black-swan")
    async def get_black_swan():
        """Tail-risk alert: composite score, stress indicators, circuit breakers."""
        try:
            ma = _get_market_analyzer()
            alert = await asyncio.to_thread(ma.black_swan.alert)
            return alert.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Black swan alert failed: {e}")
            raise HTTPException(500, f"Black swan alert failed: {e}")

    # ------------------------------------------------------------------
    # Market Context (via market_analyzer MarketContextService)
    # ------------------------------------------------------------------

    @router.get("/context")
    async def get_market_context():
        """Pre-trade gate: environment label, trading allowed, size factor, intermarket."""
        try:
            ma = _get_market_analyzer()
            ctx = await asyncio.to_thread(ma.context.assess)
            return ctx.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Market context failed: {e}")
            raise HTTPException(500, f"Market context failed: {e}")

    # ------------------------------------------------------------------
    # Screening (via market_analyzer ScreeningService)
    # ------------------------------------------------------------------

    class ScreeningRequest(BaseModel):
        tickers: list[str]
        screens: list[str] | None = None

    @router.post("/screening")
    async def run_screening(body: ScreeningRequest):
        """Find setups across tickers: breakout, momentum, mean_reversion, income."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.screening.scan, body.tickers, screens=body.screens)
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Screening failed: {e}")
            raise HTTPException(500, f"Screening failed: {e}")

    # ------------------------------------------------------------------
    # New Opportunity Endpoints (iron_condor, iron_butterfly, calendar, etc.)
    # ------------------------------------------------------------------

    @router.get("/opportunity/iron-condor/{ticker}")
    async def get_opportunity_iron_condor(ticker: str):
        """Iron condor opportunity with trade spec (strikes, expiry, sizing)."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_iron_condor, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Iron condor opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Iron condor assessment failed: {e}")

    @router.get("/opportunity/iron-butterfly/{ticker}")
    async def get_opportunity_iron_butterfly(ticker: str):
        """Iron butterfly opportunity assessment."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_iron_butterfly, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Iron butterfly opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Iron butterfly assessment failed: {e}")

    @router.get("/opportunity/calendar/{ticker}")
    async def get_opportunity_calendar(ticker: str):
        """Calendar spread opportunity with IV differential."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_calendar, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Calendar opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Calendar assessment failed: {e}")

    @router.get("/opportunity/diagonal/{ticker}")
    async def get_opportunity_diagonal(ticker: str):
        """Diagonal spread opportunity assessment."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_diagonal, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Diagonal opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Diagonal assessment failed: {e}")

    @router.get("/opportunity/mean-reversion/{ticker}")
    async def get_opportunity_mean_reversion(ticker: str):
        """Mean reversion opportunity: RSI extreme, Bollinger squeeze."""
        try:
            ma = _get_market_analyzer()
            result = await asyncio.to_thread(ma.opportunity.assess_mean_reversion, ticker.upper())
            return result.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Mean reversion opportunity failed for {ticker}: {e}")
            raise HTTPException(500, f"Mean reversion assessment failed: {e}")

    return router
