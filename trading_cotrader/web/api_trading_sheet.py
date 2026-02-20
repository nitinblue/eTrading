"""
Trading Dashboard API — Single comprehensive view for trading decisions.

Endpoints:
  GET  /api/v2/trading-dashboard/{portfolio}          — Full trading view
  POST /api/v2/trading-dashboard/{portfolio}/refresh   — Broker sync + container refresh
  POST /api/v2/trading-dashboard/{portfolio}/evaluate  — Evaluate a research template
  POST /api/v2/trading-dashboard/{portfolio}/add-whatif — Add proposed trade
  POST /api/v2/trading-dashboard/{portfolio}/book       — Convert WhatIf to real

Mounted in approval_api.py at /api/v2 prefix.
"""

from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import (
    LegORM,
    PortfolioORM,
    PositionORM,
    SymbolORM,
    TradeORM,
)
from trading_cotrader.services.pricing.probability import ProbabilityCalculator
from trading_cotrader.services.portfolio_fitness import PortfolioFitnessChecker

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)

_prob_calc = ProbabilityCalculator()
_fitness_checker = PortfolioFitnessChecker()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(val: Any) -> float:
    if val is None:
        return 0.0
    return float(val)


def _multiplier(pos: PositionORM) -> int:
    """100 for options, 1 for equity/stock positions."""
    if pos.symbol and pos.symbol.option_type:
        return 100
    return 1


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _dte_from_expiry(expiry) -> Optional[int]:
    if expiry is None:
        return None
    today = date_cls.today()
    if isinstance(expiry, datetime):
        expiry = expiry.date()
    return max(0, (expiry - today).days)


def _trade_dte(trade: TradeORM) -> Optional[int]:
    """Nearest DTE across all legs."""
    if not trade.legs:
        return None
    dtes = []
    for leg in trade.legs:
        if leg.symbol and leg.symbol.expiration:
            d = _dte_from_expiry(leg.symbol.expiration)
            if d is not None:
                dtes.append(d)
    return min(dtes) if dtes else None


def _legs_summary(trade: TradeORM) -> str:
    """Compact legs description: e.g. 'IC 480P/475P/520C/525C' or 'VS 480P/475P'."""
    if not trade.legs:
        return ''
    parts = []
    for leg in sorted(trade.legs, key=lambda l: float(l.symbol.strike or 0) if l.symbol else 0):
        sym = leg.symbol
        if not sym:
            continue
        otype = (sym.option_type or '')[0:1].upper()
        strike = int(float(sym.strike)) if sym.strike else '?'
        side = '+' if (leg.quantity or 0) > 0 else '-'
        parts.append(f"{side}{abs(leg.quantity or 1)} {strike}{otype}")
    return ' / '.join(parts)


def _strategy_label(trade: TradeORM) -> str:
    """Short strategy type label."""
    if trade.strategy and trade.strategy.strategy_type:
        return trade.strategy.strategy_type
    n_legs = len(trade.legs) if trade.legs else 0
    if n_legs >= 4:
        return 'iron_condor'
    if n_legs == 2:
        types = set()
        for l in trade.legs:
            if l.symbol:
                types.add(l.symbol.option_type)
        if len(types) == 1:
            return 'vertical_spread'
        return 'strangle'
    if n_legs == 1:
        return 'single'
    return 'custom'


# ---------------------------------------------------------------------------
# Table 1: Strategy-level rows — grouped from broker PositionORM
# ---------------------------------------------------------------------------

def _infer_strategy_type(legs: List[PositionORM]) -> str:
    """Infer strategy type from a group of broker positions."""
    n = len(legs)
    option_types = set()
    for p in legs:
        if p.symbol and p.symbol.option_type:
            option_types.add(p.symbol.option_type)

    has_puts = 'put' in option_types
    has_calls = 'call' in option_types

    if n >= 4 and has_puts and has_calls:
        return 'iron_condor'
    if n == 3 and has_puts and has_calls:
        return 'custom_3leg'
    if n == 2:
        if len(option_types) == 1:
            return 'vertical_spread'
        if has_puts and has_calls:
            return 'strangle'
    if n == 1:
        if not option_types:
            return 'equity'
        return f"single_{list(option_types)[0]}"
    return f"custom_{n}leg"


def _pos_legs_summary(legs: List[PositionORM]) -> str:
    """Compact legs description from broker positions."""
    parts = []
    for p in sorted(legs, key=lambda x: float(x.symbol.strike or 0) if x.symbol else 0):
        sym = p.symbol
        if not sym:
            continue
        otype = (sym.option_type or 'E')[0:1].upper()
        strike = int(float(sym.strike)) if sym.strike else '?'
        sign = '+' if (p.quantity or 0) > 0 else '-'
        parts.append(f"{sign}{abs(p.quantity or 1)} {strike}{otype}")
    return ' / '.join(parts)


def _compute_max_risk(legs: List[PositionORM], net_premium: float) -> float:
    """Estimate max risk from position legs.

    Equity: market value (entry_price * quantity)
    Defined risk (spreads): spread_width * contracts * 100 - |net_credit|
    Undefined risk: rough estimate from premium * 20.
    """
    # Equity positions: max risk = market value of the position
    is_equity = all(not (p.symbol and p.symbol.option_type) for p in legs)
    if is_equity:
        return abs(net_premium)

    put_strikes = sorted([float(p.symbol.strike) for p in legs
                          if p.symbol and p.symbol.strike and p.symbol.option_type == 'put'])
    call_strikes = sorted([float(p.symbol.strike) for p in legs
                           if p.symbol and p.symbol.strike and p.symbol.option_type == 'call'])

    put_width = (put_strikes[-1] - put_strikes[0]) if len(put_strikes) >= 2 else 0
    call_width = (call_strikes[-1] - call_strikes[0]) if len(call_strikes) >= 2 else 0
    spread_width = max(put_width, call_width)

    if spread_width > 0:
        qty = max(abs(p.quantity or 0) for p in legs) if legs else 1
        gross = spread_width * qty * 100
        credit = abs(net_premium) if net_premium < 0 else 0
        return max(gross - credit, 0)

    # Undefined or single leg — rough estimate
    if net_premium != 0:
        return abs(net_premium) * 20
    return 0


def _group_positions_into_strategies(
    positions: List[PositionORM],
    total_equity: float,
    total_bp: float,
) -> List[Dict]:
    """Group broker positions by underlying into strategy-level rows."""
    groups: Dict[str, List[PositionORM]] = {}
    for pos in positions:
        sym = pos.symbol
        if not sym:
            continue
        underlying = sym.ticker.split()[0] if sym.ticker else ''
        if not underlying:
            continue
        groups.setdefault(underlying, []).append(pos)

    strategies = []
    for underlying, legs in groups.items():
        strategy_type = _infer_strategy_type(legs)
        legs_summary = _pos_legs_summary(legs)

        # Net premium: entry_price * quantity * multiplier (100 for options, 1 for equity)
        net_premium = sum(_dec(p.entry_price) * (p.quantity or 0) * _multiplier(p) for p in legs)
        entry_cost_display = abs(net_premium)

        # Aggregate Greeks
        net_delta = sum(_dec(p.delta) for p in legs)
        net_gamma = sum(_dec(p.gamma) for p in legs)
        net_theta = sum(_dec(p.theta) for p in legs)
        net_vega = sum(_dec(p.vega) for p in legs)
        total_pnl = sum(_dec(p.total_pnl) for p in legs)

        # DTE — nearest expiry
        dtes = []
        for p in legs:
            if p.symbol and p.symbol.expiration:
                d = _dte_from_expiry(p.symbol.expiration)
                if d is not None:
                    dtes.append(d)
        dte = min(dtes) if dtes else None

        max_risk = _compute_max_risk(legs, net_premium)
        margin = max_risk if max_risk > 0 else entry_cost_display
        qty = max(abs(p.quantity or 0) for p in legs) if legs else 0

        strategies.append({
            'trade_id': f"grp_{underlying}",
            'underlying': underlying,
            'strategy_type': strategy_type,
            'legs_summary': legs_summary,
            'dte': dte,
            'quantity': qty,
            'entry_cost': round(net_premium, 2),
            'margin_used': round(margin, 2),
            'margin_pct_of_capital': round(margin / total_equity * 100, 2) if total_equity else 0,
            'max_risk': round(max_risk, 2),
            'max_risk_pct_margin': round(max_risk / margin * 100, 1) if margin else 0,
            'max_risk_pct_total_bp': round(max_risk / total_bp * 100, 2) if total_bp else 0,
            'net_delta': round(net_delta, 4),
            'net_theta': round(net_theta, 4),
            'net_gamma': round(net_gamma, 6),
            'net_vega': round(net_vega, 4),
            'total_pnl': round(total_pnl, 2),
            'pnl_pct': round(total_pnl / entry_cost_display * 100, 1) if entry_cost_display else 0,
            'trade_source': 'broker',
            'trade_type': 'real',
            'status': 'open',
            'opened_at': None,
            'is_open': True,
        })

    strategies.sort(key=lambda s: abs(s['max_risk']), reverse=True)
    return strategies


def _build_whatif_strategy_row(trade: TradeORM, total_equity: float, total_bp: float) -> Dict:
    """Build one WhatIf strategy row from a TradeORM + its legs."""
    dte = _trade_dte(trade)
    entry_cost = _dec(trade.entry_price)
    max_risk = _dec(trade.max_risk)
    margin = max_risk if max_risk > 0 else abs(entry_cost) * 100 if entry_cost else 0

    net_delta = _dec(trade.current_delta or trade.entry_delta)
    net_theta = _dec(trade.current_theta or trade.entry_theta)
    net_gamma = _dec(trade.current_gamma or trade.entry_gamma)
    net_vega = _dec(trade.current_vega or trade.entry_vega)
    total_pnl = _dec(trade.total_pnl)

    return {
        'trade_id': trade.id,
        'underlying': trade.underlying_symbol or '',
        'strategy_type': _strategy_label(trade),
        'legs_summary': _legs_summary(trade),
        'dte': dte,
        'quantity': max(abs(l.quantity or 0) for l in trade.legs) if trade.legs else 0,
        'entry_cost': round(entry_cost, 2),
        'margin_used': round(margin, 2),
        'margin_pct_of_capital': round(margin / total_equity * 100, 2) if total_equity else 0,
        'max_risk': round(max_risk, 2),
        'max_risk_pct_margin': round(max_risk / margin * 100, 1) if margin else 0,
        'max_risk_pct_total_bp': round(max_risk / total_bp * 100, 2) if total_bp else 0,
        'net_delta': round(net_delta, 4),
        'net_theta': round(net_theta, 4),
        'net_gamma': round(net_gamma, 6),
        'net_vega': round(net_vega, 4),
        'total_pnl': round(total_pnl, 2),
        'pnl_pct': round(total_pnl / abs(entry_cost * 100) * 100, 1) if entry_cost else 0,
        'trade_source': trade.trade_source or '',
        'trade_type': trade.trade_type or '',
        'status': trade.trade_status or '',
        'opened_at': _iso(trade.opened_at or trade.created_at),
        'is_open': trade.is_open,
    }


# ---------------------------------------------------------------------------
# Table 2: Position (leg-level) rows
# ---------------------------------------------------------------------------

def _build_position_row(pos: PositionORM) -> Dict:
    """Build one position row with entry/current Greeks + P&L attribution."""
    symbol = pos.symbol
    return {
        'id': pos.id,
        'symbol': symbol.ticker if symbol else '',
        'underlying': symbol.ticker.split()[0] if symbol and symbol.ticker else '',
        'option_type': symbol.option_type if symbol else None,
        'strike': float(symbol.strike) if symbol and symbol.strike else None,
        'expiry': _iso(symbol.expiration) if symbol else None,
        'dte': _dte_from_expiry(symbol.expiration) if symbol and symbol.expiration else None,
        'quantity': pos.quantity,
        'side': 'long' if (pos.quantity or 0) > 0 else 'short',
        # Entry state
        'entry_price': _dec(pos.entry_price),
        'entry_delta': _dec(pos.entry_delta),
        'entry_gamma': _dec(pos.entry_gamma),
        'entry_theta': _dec(pos.entry_theta),
        'entry_vega': _dec(pos.entry_vega),
        'entry_iv': _dec(pos.entry_iv),
        # Current state
        'current_price': _dec(pos.current_price),
        'delta': _dec(pos.delta),
        'gamma': _dec(pos.gamma),
        'theta': _dec(pos.theta),
        'vega': _dec(pos.vega),
        'iv': _dec(pos.current_iv),
        # P&L attribution
        'pnl_delta': _dec(pos.delta_pnl),
        'pnl_gamma': _dec(pos.gamma_pnl),
        'pnl_theta': _dec(pos.theta_pnl),
        'pnl_vega': _dec(pos.vega_pnl),
        'pnl_unexplained': _dec(pos.unexplained_pnl),
        'total_pnl': _dec(pos.total_pnl),
        'broker_pnl': _dec(pos.market_value) - _dec(pos.total_cost),
        'pnl_pct': (
            round(_dec(pos.total_pnl) / abs(_dec(pos.total_cost)) * 100, 2)
            if _dec(pos.total_cost) != 0 else 0
        ),
    }


# ---------------------------------------------------------------------------
# Table 3: Risk factors
# ---------------------------------------------------------------------------

def _build_risk_factors(positions: List[PositionORM]) -> List[Dict]:
    """Aggregate positions by underlying."""
    factors: Dict[str, Dict] = {}
    for pos in positions:
        sym = pos.symbol
        if not sym:
            continue
        underlying = sym.ticker.split()[0] if sym.ticker else ''
        if not underlying:
            continue
        is_equity = not (sym.option_type)
        if underlying not in factors:
            factors[underlying] = {
                'underlying': underlying, 'spot': 0.0,
                'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0,
                'count': 0, 'pnl': 0.0, '_is_equity': is_equity,
            }
        f = factors[underlying]
        f['delta'] += _dec(pos.delta)
        f['gamma'] += _dec(pos.gamma)
        f['theta'] += _dec(pos.theta)
        f['vega'] += _dec(pos.vega)
        f['count'] += 1
        f['pnl'] += _dec(pos.total_pnl)
        if _dec(pos.current_underlying_price) > 0:
            f['spot'] = _dec(pos.current_underlying_price)

    result = []
    total_abs_delta_dollars = 0
    for f in factors.values():
        # delta_dollars: for options delta * spot * 100 (contract multiplier),
        # for equity delta IS the share count so delta * spot is already correct.
        # Since broker populates delta as per-share delta (0-1) for options but
        # net delta for equity (= quantity), we use the stored delta * spot * 100
        # for option groups and delta * spot for equity groups.
        if f.get('_is_equity'):
            f['delta_dollars'] = round(f['delta'] * f['spot'], 2)
        else:
            f['delta_dollars'] = round(f['delta'] * f['spot'] * 100, 2)
        total_abs_delta_dollars += abs(f['delta_dollars'])

    for f in factors.values():
        result.append({
            'underlying': f['underlying'],
            'spot': round(f['spot'], 2),
            'delta': round(f['delta'], 4),
            'gamma': round(f['gamma'], 6),
            'theta': round(f['theta'], 4),
            'vega': round(f['vega'], 4),
            'delta_dollars': f['delta_dollars'],
            'concentration_pct': round(abs(f['delta_dollars']) / total_abs_delta_dollars * 100, 1) if total_abs_delta_dollars else 0,
            'count': f['count'],
            'pnl': round(f['pnl'], 2),
        })
    result.sort(key=lambda x: abs(x['delta_dollars']), reverse=True)
    return result


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EvaluateTemplateRequest(BaseModel):
    template_name: str


class AddWhatIfRequest(BaseModel):
    underlying: str
    strategy_type: str
    legs: List[Dict]
    notes: str = ""


class BookTradeRequest(BaseModel):
    whatif_trade_id: str


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_trading_sheet_router(engine: 'WorkflowEngine') -> APIRouter:
    router = APIRouter(tags=["trading-dashboard"])

    # -----------------------------------------------------------------------
    # GET /trading-dashboard/{portfolio_name}
    # -----------------------------------------------------------------------
    @router.get("/trading-dashboard/{portfolio_name}")
    async def get_trading_dashboard(portfolio_name: str):
        """Full trading view: strategies, positions, risk factors."""
        with session_scope() as session:
            portfolio = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.name == portfolio_name)
                .first()
            )
            if not portfolio:
                raise HTTPException(404, f"Portfolio '{portfolio_name}' not found")

            equity = _dec(portfolio.total_equity)
            cash = _dec(portfolio.cash_balance)
            buying_power = _dec(portfolio.buying_power)
            margin_used = equity - cash if equity else 0
            margin_pct = (margin_used / equity * 100) if equity else 0

            # --- Positions (broker-synced, for Table 2 + risk factors) ---
            positions = (
                session.query(PositionORM)
                .filter(PositionORM.portfolio_id == portfolio.id)
                .all()
            )
            position_rows = [_build_position_row(p) for p in positions]

            # Aggregate portfolio Greeks from positions
            net_delta = sum(_dec(p.delta) for p in positions)
            net_gamma = sum(_dec(p.gamma) for p in positions)
            net_theta = sum(_dec(p.theta) for p in positions)
            net_vega = sum(_dec(p.vega) for p in positions)

            # --- Table 1: Strategy-level from broker positions ---
            real_strategies = _group_positions_into_strategies(
                positions, equity, buying_power,
            )

            # --- WhatIf trades from TradeORM ---
            whatif_orm = (
                session.query(TradeORM)
                .filter(
                    TradeORM.portfolio_id == portfolio.id,
                    TradeORM.is_open == True,
                    TradeORM.trade_type == 'what_if',
                )
                .all()
            )
            whatif_trades = [
                _build_whatif_strategy_row(t, equity, buying_power)
                for t in whatif_orm
            ]

            # WhatIf Greeks impact
            whatif_delta = sum(w['net_delta'] for w in whatif_trades)
            whatif_theta = sum(w['net_theta'] for w in whatif_trades)

            # Risk factors
            risk_factor_rows = _build_risk_factors(positions)

            # VaR
            var_95 = _dec(portfolio.var_1d_95)
            theta_var = abs(net_theta / var_95) if var_95 else 0

            return {
                'portfolio': {
                    'name': portfolio.name,
                    'portfolio_type': portfolio.portfolio_type,
                    'broker': portfolio.broker,
                    'total_equity': equity,
                    'cash_balance': cash,
                    'buying_power': buying_power,
                    'margin_used': round(margin_used, 2),
                    'margin_used_pct': round(margin_pct, 1),
                    'net_delta': round(net_delta, 4),
                    'net_gamma': round(net_gamma, 6),
                    'net_theta': round(net_theta, 4),
                    'net_vega': round(net_vega, 4),
                    'net_delta_with_whatif': round(net_delta + whatif_delta, 4),
                    'net_theta_with_whatif': round(net_theta + whatif_theta, 4),
                    'var_1d_95': round(var_95, 2),
                    'theta_var_ratio': round(theta_var, 4),
                    'capital_deployed_pct': round(margin_pct, 1),
                    'max_delta': _dec(portfolio.max_portfolio_delta),
                    'delta_utilization_pct': round(
                        abs(net_delta) / _dec(portfolio.max_portfolio_delta) * 100, 1
                    ) if _dec(portfolio.max_portfolio_delta) else 0,
                    'open_positions': len(positions),
                    'open_strategies': len(real_strategies),
                    'whatif_count': len(whatif_trades),
                },
                'strategies': real_strategies,
                'positions': position_rows,
                'whatif_trades': whatif_trades,
                'risk_factors': risk_factor_rows,
            }

    # -----------------------------------------------------------------------
    # POST /trading-dashboard/{portfolio_name}/refresh
    # -----------------------------------------------------------------------
    @router.post("/trading-dashboard/{portfolio_name}/refresh")
    async def refresh_dashboard(
        portfolio_name: str,
        snapshot: bool = Query(False, description="Also capture daily snapshot"),
    ):
        """Trigger broker sync + container refresh. Optionally capture snapshot."""
        # 1. Broker sync
        sync_count = 0
        try:
            engine._sync_broker_positions()
            sync_count = 1
        except Exception as e:
            logger.warning(f"Broker sync during refresh: {e}")

        # 2. Container refresh
        try:
            engine._refresh_containers()
        except Exception as e:
            logger.warning(f"Container refresh during refresh: {e}")

        # 3. Optional snapshot
        snapshot_result = None
        if snapshot:
            try:
                snapshot_result = engine._capture_snapshots()
            except Exception as e:
                logger.warning(f"Snapshot during refresh: {e}")

        return {
            'success': True,
            'broker_synced': sync_count > 0,
            'containers_refreshed': True,
            'snapshot_captured': snapshot_result is not None,
        }

    # -----------------------------------------------------------------------
    # POST /trading-dashboard/{portfolio_name}/evaluate
    # -----------------------------------------------------------------------
    @router.post("/trading-dashboard/{portfolio_name}/evaluate")
    async def evaluate_template(portfolio_name: str, body: EvaluateTemplateRequest):
        """Evaluate a research template against the portfolio."""
        try:
            from trading_cotrader.services.research.template_loader import load_research_templates
            from trading_cotrader.services.research.condition_evaluator import ConditionEvaluator
            from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService
        except ImportError as e:
            raise HTTPException(500, f"Missing dependency: {e}")

        templates = load_research_templates()
        template = templates.get(body.template_name)
        if not template:
            raise HTTPException(404, f"Template '{body.template_name}' not found. Available: {list(templates.keys())}")

        with session_scope() as session:
            portfolio = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio_name).first()
            if not portfolio:
                raise HTTPException(404, f"Portfolio '{portfolio_name}' not found")

            positions = session.query(PositionORM).filter(PositionORM.portfolio_id == portfolio.id).all()
            equity = _dec(portfolio.total_equity)
            net_delta = sum(_dec(p.delta) for p in positions)
            risk_factor_rows = _build_risk_factors(positions)

            portfolio_state = {
                'net_delta': net_delta,
                'total_equity': equity,
                'buying_power': _dec(portfolio.buying_power),
                'margin_used': equity - _dec(portfolio.cash_balance),
                'var_1d_95': _dec(portfolio.var_1d_95),
                'open_positions': len(positions),
                'exposure_by_underlying': {f['underlying']: abs(f['delta_dollars']) for f in risk_factor_rows},
            }
            risk_limits = {
                'max_delta': _dec(portfolio.max_portfolio_delta),
                'max_positions': 50,
                'max_var_pct': 2.0,
                'max_concentration_pct': _dec(portfolio.max_concentration_pct) or 25,
                'max_margin_pct': 50.0,
            }

        ta_service = TechnicalAnalysisService()
        evaluator = ConditionEvaluator()
        global_ctx = {}
        if hasattr(engine, 'context'):
            global_ctx['vix'] = engine.context.get('vix', 20)

        evaluated = []
        triggered_count = 0

        for symbol in template.universe:
            try:
                snapshot = ta_service.get_snapshot(symbol)
            except Exception as e:
                evaluated.append({'symbol': symbol, 'triggered': False, 'conditions': {}, 'error': str(e)})
                continue

            all_passed, details = evaluator.evaluate_all(template.entry_conditions, snapshot, global_ctx)
            conditions_display = {}
            for indicator, detail in details.items():
                conditions_display[indicator] = {
                    'passed': detail.get('passed', False),
                    'actual': detail.get('actual'),
                    'target': detail.get('target'),
                    'operator': detail.get('operator', ''),
                }

            symbol_result = {
                'symbol': symbol,
                'triggered': all_passed,
                'conditions': conditions_display,
                'snapshot': {
                    'price': float(snapshot.current_price),
                    'rsi_14': snapshot.rsi_14,
                    'iv_rank': snapshot.iv_rank,
                },
            }

            if all_passed:
                triggered_count += 1
                proposed = _build_proposed_from_template(template, symbol, snapshot, portfolio_state, risk_limits)
                symbol_result['proposed_trade'] = proposed

            evaluated.append(symbol_result)

        summary_parts = [f"{triggered_count} of {len(template.universe)} symbols triggered."]
        for ev in evaluated:
            if ev.get('triggered') and ev.get('proposed_trade'):
                pt = ev['proposed_trade']
                summary_parts.append(
                    f"{ev['symbol']} {pt.get('strategy_type', '?')}: "
                    f"POP {pt.get('pop', 0)*100:.0f}%, EV ${pt.get('expected_value', 0):+.0f}."
                )

        return {
            'template': {
                'name': template.name,
                'display_name': template.display_name,
                'description': template.description,
                'universe': template.universe,
            },
            'evaluated_symbols': evaluated,
            'summary': ' '.join(summary_parts),
        }

    # -----------------------------------------------------------------------
    # POST /trading-dashboard/{portfolio_name}/add-whatif
    # -----------------------------------------------------------------------
    @router.post("/trading-dashboard/{portfolio_name}/add-whatif")
    async def add_whatif(portfolio_name: str, body: AddWhatIfRequest):
        """Add a proposed trade to WhatIf."""
        with session_scope() as session:
            portfolio = session.query(PortfolioORM).filter(PortfolioORM.name == portfolio_name).first()
            if not portfolio:
                raise HTTPException(404, f"Portfolio '{portfolio_name}' not found")

            trade_id = str(uuid.uuid4())
            trade = TradeORM(
                id=trade_id, portfolio_id=portfolio.id,
                trade_type='what_if', trade_status='evaluated',
                underlying_symbol=body.underlying, trade_source='trading_dashboard',
                is_open=True, notes=body.notes or 'Added from Trading Dashboard',
            )

            total_delta = total_gamma = total_theta = total_vega = 0.0
            for leg_data in body.legs:
                sym_id = str(uuid.uuid4())
                symbol = SymbolORM(
                    id=sym_id,
                    ticker=f"{body.underlying} {leg_data.get('expiration', '')} "
                           f"{leg_data.get('strike', '')} {leg_data.get('option_type', '')}".strip(),
                    asset_type='option',
                    option_type=leg_data.get('option_type'),
                    strike=Decimal(str(leg_data.get('strike', 0))),
                    expiration=datetime.fromisoformat(leg_data['expiration']) if leg_data.get('expiration') else None,
                )
                session.add(symbol)
                leg = LegORM(
                    id=str(uuid.uuid4()), trade_id=trade_id, symbol_id=sym_id,
                    quantity=leg_data.get('quantity', 0), side=leg_data.get('side', 'buy'),
                )
                session.add(leg)
                total_delta += float(leg_data.get('delta', 0))
                total_gamma += float(leg_data.get('gamma', 0))
                total_theta += float(leg_data.get('theta', 0))
                total_vega += float(leg_data.get('vega', 0))

            trade.entry_delta = Decimal(str(total_delta))
            trade.entry_gamma = Decimal(str(total_gamma))
            trade.entry_theta = Decimal(str(total_theta))
            trade.entry_vega = Decimal(str(total_vega))
            trade.current_delta = trade.entry_delta
            trade.current_gamma = trade.entry_gamma
            trade.current_theta = trade.entry_theta
            trade.current_vega = trade.entry_vega
            session.add(trade)
            session.flush()

            return {'success': True, 'trade_id': trade_id}

    # -----------------------------------------------------------------------
    # POST /trading-dashboard/{portfolio_name}/book
    # -----------------------------------------------------------------------
    @router.post("/trading-dashboard/{portfolio_name}/book")
    async def book_trade(portfolio_name: str, body: BookTradeRequest):
        """Convert WhatIf to paper trade."""
        with session_scope() as session:
            trade = session.query(TradeORM).get(body.whatif_trade_id)
            if not trade:
                raise HTTPException(404, f"Trade '{body.whatif_trade_id}' not found")
            if trade.trade_type != 'what_if':
                raise HTTPException(400, f"Trade is not WhatIf (type={trade.trade_type})")
            portfolio = session.query(PortfolioORM).get(trade.portfolio_id)
            if not portfolio or portfolio.name != portfolio_name:
                raise HTTPException(400, "Trade does not belong to this portfolio")

            trade.trade_type = 'paper'
            trade.trade_status = 'pending'
            trade.notes = (trade.notes or '') + ' | Booked from Trading Dashboard'
            return {'success': True, 'trade_id': trade.id}

    return router


# ---------------------------------------------------------------------------
# Template → Proposed Trade builder
# ---------------------------------------------------------------------------

def _build_proposed_from_template(template, symbol, snapshot, portfolio_state, risk_limits) -> Dict:
    strategies = template.trade_strategy.strategies
    if not strategies:
        return {'error': 'No strategies defined'}

    strategy = strategies[0]
    spot = float(snapshot.current_price)
    iv = (snapshot.iv_rank or 25) / 100
    dte = strategy.dte_target or 45

    legs = _construct_legs(strategy, spot, iv, dte, symbol)

    payoff = {}
    if legs:
        try:
            result = _prob_calc.compute_trade_payoff(legs=legs, spot=spot, iv=max(iv, 0.10), dte=dte)
            payoff = {
                'pop': round(result.probability_of_profit, 4),
                'expected_value': round(result.expected_value, 2),
                'breakevens': [round(b, 2) for b in result.breakeven_prices],
            }
        except Exception as e:
            logger.warning(f"Payoff calc error for {symbol}: {e}")

    trade_delta = -(strategy.short_delta or 0.30)
    trade_margin = payoff.get('max_loss', 500)

    fitness = _fitness_checker.check_trade_fitness(
        portfolio_state,
        {'underlying': symbol, 'delta': trade_delta * 100, 'margin_required': trade_margin, 'var_impact': abs(trade_delta) * spot * 0.02},
        risk_limits,
    )

    return {'strategy_type': strategy.strategy_type, 'legs': legs, 'dte': dte, **payoff, **fitness.to_dict()}


def _construct_legs(strategy, spot, iv, dte, symbol) -> List[Dict]:
    stype = strategy.strategy_type.lower()

    if stype in ('vertical_spread', 'put_credit_spread', 'call_credit_spread'):
        opt_type = strategy.option_type or 'put'
        short_delta = strategy.short_delta or 0.30
        wing_width = strategy.wing_width_pct or 0.03
        if opt_type == 'put':
            short_strike = round(spot * (1 - short_delta * iv), 0)
            long_strike = round(short_strike - spot * wing_width, 0)
        else:
            short_strike = round(spot * (1 + short_delta * iv), 0)
            long_strike = round(short_strike + spot * wing_width, 0)
        return [
            {'strike': short_strike, 'option_type': opt_type, 'quantity': -1, 'side': 'sell'},
            {'strike': long_strike, 'option_type': opt_type, 'quantity': 1, 'side': 'buy'},
        ]

    if stype in ('iron_condor', 'iron_butterfly'):
        put_delta = strategy.put_delta or 0.20
        call_delta = strategy.call_delta or 0.20
        wing = strategy.wing_width_pct or 0.03
        put_short = round(spot * (1 - put_delta * iv), 0)
        put_long = round(put_short - spot * wing, 0)
        call_short = round(spot * (1 + call_delta * iv), 0)
        call_long = round(call_short + spot * wing, 0)
        return [
            {'strike': put_long, 'option_type': 'put', 'quantity': 1, 'side': 'buy'},
            {'strike': put_short, 'option_type': 'put', 'quantity': -1, 'side': 'sell'},
            {'strike': call_short, 'option_type': 'call', 'quantity': -1, 'side': 'sell'},
            {'strike': call_long, 'option_type': 'call', 'quantity': 1, 'side': 'buy'},
        ]

    if stype in ('strangle', 'short_strangle'):
        put_delta = strategy.put_delta or 0.20
        call_delta = strategy.call_delta or 0.20
        return [
            {'strike': round(spot * (1 - put_delta * iv), 0), 'option_type': 'put', 'quantity': -1, 'side': 'sell'},
            {'strike': round(spot * (1 + call_delta * iv), 0), 'option_type': 'call', 'quantity': -1, 'side': 'sell'},
        ]

    if stype in ('single', 'naked_put', 'naked_call'):
        opt_type = strategy.option_type or 'put'
        delta = strategy.short_delta or strategy.delta_target or 0.30
        strike = round(spot * (1 - delta * iv), 0) if opt_type == 'put' else round(spot * (1 + delta * iv), 0)
        return [{'strike': strike, 'option_type': opt_type, 'quantity': -1, 'side': 'sell'}]

    if stype in ('calendar_spread', 'double_calendar'):
        opt_type = strategy.option_type or 'put'
        strike = round(spot, 0)
        return [
            {'strike': strike, 'option_type': opt_type, 'quantity': -1, 'side': 'sell'},
            {'strike': strike, 'option_type': opt_type, 'quantity': 1, 'side': 'buy'},
        ]

    short_strike = round(spot * 0.95, 0)
    long_strike = round(spot * 0.92, 0)
    return [
        {'strike': short_strike, 'option_type': 'put', 'quantity': -1, 'side': 'sell'},
        {'strike': long_strike, 'option_type': 'put', 'quantity': 1, 'side': 'buy'},
    ]
