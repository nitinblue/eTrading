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
from trading_cotrader.containers.position_container import PositionState
from trading_cotrader.containers.trade_container import TradeState

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(val: Any) -> float:
    if val is None:
        return 0.0
    return float(val)


def _multiplier_pos(pos: PositionState) -> int:
    """100 for options, 1 for equity/stock positions."""
    return 100 if pos.is_option else 1


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
# WhatIf: live Greeks + quotes from TastyTrade DXLink
# ---------------------------------------------------------------------------

def _leg_streamer_symbol(underlying: str, leg: LegORM) -> Optional[str]:
    """Build TastyTrade DXLink streamer symbol from a WhatIf leg.

    Format: .{TICKER}{YYMMDD}{C/P}{STRIKE_INT}
    Example: .META260408P609
    """
    sym = leg.symbol
    if not sym or not sym.expiration or not sym.strike or not sym.option_type:
        return None
    try:
        exp = sym.expiration
        if isinstance(exp, datetime):
            exp = exp.date()
        elif isinstance(exp, str):
            exp = datetime.fromisoformat(exp).date()
        yymmdd = exp.strftime('%y%m%d')
        cp = 'C' if sym.option_type.lower() == 'call' else 'P'
        strike_int = int(float(sym.strike))
        return f".{underlying}{yymmdd}{cp}{strike_int}"
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Could not build streamer symbol for leg {leg.id}: {e}")
        return None


def _refresh_whatif_greeks_from_broker(
    whatif_trades: List[TradeORM],
    engine: 'WorkflowEngine',
    session,
) -> None:
    """Fetch live Greeks + quotes from TastyTrade DXLink for all WhatIf legs.

    Constructs streamer symbols, batch-fetches Greeks and quotes,
    updates LegORM + TradeORM in-place and persists to DB.
    """
    adapter = engine._adapters.get('tastytrade') if hasattr(engine, '_adapters') else None
    if not adapter:
        logger.debug("No TastyTrade adapter — WhatIf Greeks not refreshed")
        return

    # Collect all streamer symbols across all trades
    streamer_to_legs: Dict[str, List[tuple]] = {}  # sym -> [(trade, leg), ...]
    all_symbols: List[str] = []

    for trade in whatif_trades:
        underlying = trade.underlying_symbol or ''
        if not underlying or not trade.legs:
            continue
        for leg in trade.legs:
            ss = _leg_streamer_symbol(underlying, leg)
            if ss:
                streamer_to_legs.setdefault(ss, []).append((trade, leg))
                if ss not in streamer_to_legs or len(streamer_to_legs[ss]) == 1:
                    all_symbols.append(ss)

    if not all_symbols:
        return

    # Batch fetch from broker
    broker_greeks: Dict = {}
    broker_quotes: Dict = {}
    try:
        logger.info(f"WhatIf refresh: fetching Greeks for {len(all_symbols)} symbols")
        broker_greeks = adapter.get_greeks(all_symbols)
        logger.info(f"WhatIf refresh: got Greeks for {len(broker_greeks)}/{len(all_symbols)}")
    except Exception as e:
        logger.warning(f"WhatIf Greeks fetch failed: {e}")

    try:
        broker_quotes = adapter.get_quotes(all_symbols)
        logger.info(f"WhatIf refresh: got quotes for {len(broker_quotes)}/{len(all_symbols)}")
    except Exception as e:
        logger.warning(f"WhatIf quotes fetch failed: {e}")

    if not broker_greeks and not broker_quotes:
        return

    # Apply to ORM objects and aggregate at trade level
    trade_greeks: Dict[str, Dict[str, float]] = {}  # trade_id -> {delta, gamma, ...}

    for ss, pairs in streamer_to_legs.items():
        greeks = broker_greeks.get(ss)
        quote = broker_quotes.get(ss)

        for trade, leg in pairs:
            qty = leg.quantity or 0
            multiplier = 100

            # Update leg Greeks from live broker data
            if greeks:
                per_d = float(greeks.delta)
                per_g = float(greeks.gamma)
                per_t = float(greeks.theta)
                per_v = float(greeks.vega)

                pos_d = per_d * qty * multiplier
                pos_g = per_g * abs(qty) * multiplier
                pos_t = per_t * qty * multiplier
                pos_v = per_v * qty * multiplier

                leg.delta = Decimal(str(round(pos_d, 4)))
                leg.gamma = Decimal(str(round(pos_g, 6)))
                leg.theta = Decimal(str(round(pos_t, 4)))
                leg.vega = Decimal(str(round(pos_v, 4)))

                # Accumulate for trade-level
                tid = trade.id
                if tid not in trade_greeks:
                    trade_greeks[tid] = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
                trade_greeks[tid]['delta'] += pos_d
                trade_greeks[tid]['gamma'] += pos_g
                trade_greeks[tid]['theta'] += pos_t
                trade_greeks[tid]['vega'] += pos_v

            # Update leg price from live quotes (mid price)
            if quote:
                bid = quote.get('bid', 0)
                ask = quote.get('ask', 0)
                mid = (bid + ask) / 2 if bid and ask else bid or ask
                if mid > 0:
                    leg.current_price = Decimal(str(round(mid, 4)))

    # Apply trade-level aggregated Greeks
    for trade in whatif_trades:
        tg = trade_greeks.get(trade.id)
        if tg:
            trade.current_delta = Decimal(str(round(tg['delta'], 4)))
            trade.current_gamma = Decimal(str(round(tg['gamma'], 6)))
            trade.current_theta = Decimal(str(round(tg['theta'], 4)))
            trade.current_vega = Decimal(str(round(tg['vega'], 4)))

        # Compute entry_price from leg mid prices if not set or stale
        if trade.legs:
            net_premium = 0.0
            for leg in trade.legs:
                price = _dec(leg.current_price or leg.entry_price)
                net_premium += price * (leg.quantity or 0)
            if net_premium != 0:
                trade.entry_price = Decimal(str(round(net_premium, 4)))

        # Compute max_risk from leg structure (spread width * multiplier - premium)
        if trade.legs:
            strikes = sorted(
                [float(l.symbol.strike) for l in trade.legs if l.symbol and l.symbol.strike],
            )
            if len(strikes) >= 2:
                # Width of widest spread wing
                width = max(
                    strikes[i + 1] - strikes[i] for i in range(len(strikes) - 1)
                )
                net_credit = abs(_dec(trade.entry_price)) * 100
                max_loss = width * 100 - net_credit
                if max_loss > 0:
                    trade.max_risk = Decimal(str(round(max_loss, 2)))

    # Persist updated values
    try:
        session.flush()
    except Exception as e:
        logger.warning(f"WhatIf Greeks DB flush: {e}")


# ---------------------------------------------------------------------------
# Table 1: Strategy-level rows — grouped from broker PositionORM
# ---------------------------------------------------------------------------

def _infer_strategy_type(legs: List[PositionState]) -> str:
    """Infer strategy type from a group of container positions."""
    n = len(legs)
    option_types = set()
    for p in legs:
        if p.option_type:
            option_types.add(p.option_type.lower())

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


def _pos_legs_summary(legs: List[PositionState]) -> str:
    """Compact legs description from container positions."""
    parts = []
    for p in sorted(legs, key=lambda x: float(x.strike or 0)):
        otype = (p.option_type or 'E')[0:1].upper()
        strike = int(float(p.strike)) if p.strike else '?'
        sign = '+' if (p.quantity or 0) > 0 else '-'
        parts.append(f"{sign}{abs(p.quantity or 1)} {strike}{otype}")
    return ' / '.join(parts)


def _compute_max_risk(legs: List[PositionState], net_premium: float) -> float:
    """Estimate max risk from container position legs.

    Equity: market value (entry_price * quantity)
    Defined risk (spreads): spread_width * contracts * 100 - |net_credit|
    Undefined risk: rough estimate from premium * 20.
    """
    # Equity positions: max risk = market value of the position
    is_equity = all(not p.is_option for p in legs)
    if is_equity:
        return abs(net_premium)

    put_strikes = sorted([float(p.strike) for p in legs
                          if p.strike and p.option_type and p.option_type.lower() == 'put'])
    call_strikes = sorted([float(p.strike) for p in legs
                           if p.strike and p.option_type and p.option_type.lower() == 'call'])

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
    positions: List[PositionState],
    total_equity: float,
    total_bp: float,
) -> List[Dict]:
    """Group container positions by underlying into strategy-level rows."""
    groups: Dict[str, List[PositionState]] = {}
    for pos in positions:
        underlying = pos.underlying
        if not underlying:
            continue
        groups.setdefault(underlying, []).append(pos)

    strategies = []
    for underlying, legs in groups.items():
        strategy_type = _infer_strategy_type(legs)
        legs_summary = _pos_legs_summary(legs)

        # Net premium: entry_price * quantity * multiplier (100 for options, 1 for equity)
        net_premium = sum(_dec(p.entry_price) * (p.quantity or 0) * _multiplier_pos(p) for p in legs)
        entry_cost_display = abs(net_premium)

        # Aggregate Greeks
        net_delta = sum(_dec(p.delta) for p in legs)
        net_gamma = sum(_dec(p.gamma) for p in legs)
        net_theta = sum(_dec(p.theta) for p in legs)
        net_vega = sum(_dec(p.vega) for p in legs)
        total_pnl = sum(_dec(p.unrealized_pnl) for p in legs)

        # DTE — nearest expiry
        dtes = [p.dte for p in legs if p.dte is not None]
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


def _build_whatif_position_rows_from_container(trade: TradeState) -> List[Dict]:
    """Build position-like rows from container TradeState legs."""
    rows = []
    for leg in trade.legs:
        rows.append({
            'id': leg.leg_id,
            'symbol': leg.symbol,
            'underlying': leg.underlying or trade.underlying,
            'option_type': leg.option_type,
            'strike': float(leg.strike) if leg.strike else None,
            'expiry': leg.expiry,
            'dte': _dte_from_expiry(leg.expiry) if leg.expiry else None,
            'quantity': leg.quantity,
            'side': 'long' if leg.is_long else 'short',
            'entry_price': _dec(leg.entry_price),
            'entry_delta': 0.0, 'entry_gamma': 0.0, 'entry_theta': 0.0,
            'entry_vega': 0.0, 'entry_iv': 0.0,
            'current_price': _dec(leg.current_price or leg.entry_price),
            'delta': _dec(leg.delta),
            'gamma': _dec(leg.gamma),
            'theta': _dec(leg.theta),
            'vega': _dec(leg.vega),
            'iv': 0.0,
            'pnl_delta': 0.0, 'pnl_gamma': 0.0, 'pnl_theta': 0.0,
            'pnl_vega': 0.0, 'pnl_unexplained': 0.0,
            'total_pnl': 0.0, 'broker_pnl': 0.0, 'pnl_pct': 0.0,
            'trade_type': 'what_if',
            'trade_id': trade.trade_id,
        })
    return rows


def _build_whatif_position_rows(trade: TradeORM) -> List[Dict]:
    """Build position-like rows from WhatIf trade legs (for merged positions table)."""
    rows = []
    for leg in (trade.legs or []):
        sym = leg.symbol
        delta = _dec(leg.delta or leg.entry_delta)
        gamma = _dec(leg.gamma or leg.entry_gamma)
        theta = _dec(leg.theta or leg.entry_theta)
        vega = _dec(leg.vega or leg.entry_vega)
        rows.append({
            'id': leg.id,
            'symbol': sym.ticker if sym else '',
            'underlying': trade.underlying_symbol or '',
            'option_type': sym.option_type if sym else None,
            'strike': float(sym.strike) if sym and sym.strike else None,
            'expiry': _iso(sym.expiration) if sym else None,
            'dte': _dte_from_expiry(sym.expiration) if sym and sym.expiration else None,
            'quantity': leg.quantity or 0,
            'side': 'long' if (leg.quantity or 0) > 0 else 'short',
            'entry_price': _dec(leg.entry_price),
            'entry_delta': _dec(leg.entry_delta),
            'entry_gamma': _dec(leg.entry_gamma),
            'entry_theta': _dec(leg.entry_theta),
            'entry_vega': _dec(leg.entry_vega),
            'entry_iv': _dec(leg.entry_iv),
            'current_price': _dec(leg.current_price or leg.entry_price),
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'iv': _dec(leg.current_iv or leg.entry_iv),
            'pnl_delta': 0.0, 'pnl_gamma': 0.0, 'pnl_theta': 0.0,
            'pnl_vega': 0.0, 'pnl_unexplained': 0.0,
            'total_pnl': 0.0, 'broker_pnl': 0.0, 'pnl_pct': 0.0,
            # WhatIf markers
            'trade_type': 'what_if',
            'trade_id': trade.id,
        })
    return rows


def _build_whatif_risk_factors(
    whatif_strategies: List[Dict],
    spot_by_underlying: Optional[Dict[str, float]] = None,
) -> List[Dict]:
    """Build risk factor rows from WhatIf strategy-level data."""
    spots = spot_by_underlying or {}
    factors: Dict[str, Dict] = {}
    for t in whatif_strategies:
        underlying = t.get('underlying', '')
        if not underlying:
            continue
        if underlying not in factors:
            factors[underlying] = {
                'underlying': underlying,
                'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0,
                'count': 0, 'pnl': 0.0,
            }
        f = factors[underlying]
        f['delta'] += t.get('net_delta', 0)
        f['gamma'] += t.get('net_gamma', 0)
        f['theta'] += t.get('net_theta', 0)
        f['vega'] += t.get('net_vega', 0)
        f['count'] += 1
        f['pnl'] += t.get('total_pnl', 0)

    result = []
    for f in factors.values():
        spot = spots.get(f['underlying'], 0.0)
        delta_dollars = round(f['delta'] * spot, 2) if spot else 0.0
        result.append({
            'underlying': f['underlying'],
            'spot': spot,
            'delta': round(f['delta'], 4),
            'gamma': round(f['gamma'], 6),
            'theta': round(f['theta'], 4),
            'vega': round(f['vega'], 4),
            'delta_dollars': delta_dollars,
            'concentration_pct': 0.0,
            'count': f['count'],
            'pnl': round(f['pnl'], 2),
        })
    return result


def _build_whatif_strategy_row(trade, total_equity: float, total_bp: float) -> Dict:
    """Build one WhatIf strategy row from TradeState (container) or TradeORM."""
    is_container = isinstance(trade, TradeState)

    if is_container:
        dte = trade.dte
        entry_cost = _dec(trade.entry_price)
        max_risk = _dec(trade.max_loss)
        net_delta = _dec(trade.delta)
        net_theta = _dec(trade.theta)
        net_gamma = _dec(trade.gamma)
        net_vega = _dec(trade.vega)
        total_pnl = 0.0  # Container tracks current - entry separately
        trade_id = trade.trade_id
        underlying = trade.underlying or ''
        legs_list = trade.legs
        n_legs = len(legs_list)
        strategy_type = trade.strategy_type or 'custom'
        trade_source = ''
        trade_type = trade.trade_type or ''
        status = trade.trade_status or ''
        opened_at = _iso(trade.created_at)
        is_open = True  # WhatIf in container are always open
        # Legs summary from container legs
        parts = []
        for leg in sorted(legs_list, key=lambda l: float(l.strike or 0)):
            otype = (leg.option_type or 'E')[0:1].upper()
            strike = int(float(leg.strike)) if leg.strike else '?'
            sign = '+' if (leg.quantity or 0) > 0 else '-'
            parts.append(f"{sign}{abs(leg.quantity or 1)} {strike}{otype}")
        legs_summary = ' / '.join(parts)
        qty = max(abs(l.quantity or 0) for l in legs_list) if legs_list else 0
    else:
        dte = _trade_dte(trade)
        entry_cost = _dec(trade.entry_price)
        max_risk = _dec(trade.max_risk)
        net_delta = _dec(trade.current_delta or trade.entry_delta)
        net_theta = _dec(trade.current_theta or trade.entry_theta)
        net_gamma = _dec(trade.current_gamma or trade.entry_gamma)
        net_vega = _dec(trade.current_vega or trade.entry_vega)
        total_pnl = _dec(trade.total_pnl)
        trade_id = trade.id
        underlying = trade.underlying_symbol or ''
        strategy_type = _strategy_label(trade)
        legs_summary = _legs_summary(trade)
        qty = max(abs(l.quantity or 0) for l in trade.legs) if trade.legs else 0
        trade_source = trade.trade_source or ''
        trade_type = trade.trade_type or ''
        status = trade.trade_status or ''
        opened_at = _iso(trade.opened_at or trade.created_at)
        is_open = trade.is_open

    margin = max_risk if max_risk > 0 else abs(entry_cost) * 100 if entry_cost else 0

    return {
        'trade_id': trade_id,
        'underlying': underlying,
        'strategy_type': strategy_type,
        'legs_summary': legs_summary,
        'dte': dte,
        'quantity': qty,
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
        'trade_source': trade_source,
        'trade_type': trade_type,
        'status': status,
        'opened_at': opened_at,
        'is_open': is_open,
    }


# ---------------------------------------------------------------------------
# Table 2: Position (leg-level) rows
# ---------------------------------------------------------------------------

def _build_position_row(pos: PositionState) -> Dict:
    """Build one position row from container PositionState."""
    return {
        'id': pos.position_id,
        'symbol': pos.symbol,
        'underlying': pos.underlying,
        'option_type': pos.option_type,
        'strike': float(pos.strike) if pos.strike else None,
        'expiry': pos.expiry,
        'dte': pos.dte,
        'quantity': pos.quantity,
        'side': 'long' if pos.is_long else 'short',
        # Entry state
        'entry_price': _dec(pos.entry_price),
        'entry_delta': 0.0,  # Not tracked separately in container
        'entry_gamma': 0.0,
        'entry_theta': 0.0,
        'entry_vega': 0.0,
        'entry_iv': 0.0,
        # Current state
        'current_price': _dec(pos.current_price),
        'delta': _dec(pos.delta),
        'gamma': _dec(pos.gamma),
        'theta': _dec(pos.theta),
        'vega': _dec(pos.vega),
        'iv': _dec(pos.iv),
        # P&L attribution
        'pnl_delta': _dec(pos.pnl_delta),
        'pnl_gamma': _dec(pos.pnl_gamma),
        'pnl_theta': _dec(pos.pnl_theta),
        'pnl_vega': _dec(pos.pnl_vega),
        'pnl_unexplained': _dec(pos.pnl_unexplained),
        'total_pnl': _dec(pos.unrealized_pnl),
        'broker_pnl': _dec(pos.market_value) - _dec(pos.entry_value),
        'pnl_pct': (
            round(_dec(pos.unrealized_pnl) / abs(_dec(pos.entry_value)) * 100, 2)
            if _dec(pos.entry_value) != 0 else 0
        ),
    }


# ---------------------------------------------------------------------------
# Table 3: Risk factors
# ---------------------------------------------------------------------------

def _build_risk_factors_from_container(risk_factor_container) -> List[Dict]:
    """Build risk factor rows from RiskFactorContainer (already aggregated)."""
    grid_rows = risk_factor_container.to_grid_rows()
    # Map container grid format to trading dashboard format
    result = []
    for row in grid_rows:
        result.append({
            'underlying': row['underlying'],
            'spot': row['spot'],
            'delta': row['delta'],
            'gamma': row['gamma'],
            'theta': row['theta'],
            'vega': row['vega'],
            'delta_dollars': row['delta_$'],
            'concentration_pct': row['concentration'],
            'count': row['positions'],
            'pnl': row['pnl'],
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
    entry_price: Optional[float] = None
    max_risk: Optional[float] = None


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
        """Full trading view: strategies, positions, risk factors.

        ALL data comes from containers (Steward's PortfolioBundle + Scout's ResearchContainer).
        No direct DB queries. Containers are populated by Steward.populate() and refreshed
        via POST /refresh.
        """
        cm = engine.container_manager
        if not cm:
            raise HTTPException(503, "Container manager not initialized")

        bundle = cm.get_bundle(portfolio_name)
        if not bundle or not bundle.portfolio.state:
            raise HTTPException(404, f"Portfolio bundle '{portfolio_name}' not found or not loaded")

        pstate = bundle.portfolio.state
        positions = bundle.positions.get_all()
        risk_factors = bundle.risk_factors
        whatif_trades_container = bundle.trades.get_what_if_trades()

        # Portfolio summary from container
        equity = float(pstate.total_equity)
        cash = float(pstate.cash_balance)
        buying_power = float(pstate.buying_power)
        margin_used = equity - cash if equity else 0
        margin_pct = (margin_used / equity * 100) if equity else 0

        # Position rows from container
        position_rows = [_build_position_row(p) for p in positions]

        # Aggregate portfolio Greeks from container positions
        net_delta = sum(_dec(p.delta) for p in positions)
        net_gamma = sum(_dec(p.gamma) for p in positions)
        net_theta = sum(_dec(p.theta) for p in positions)
        net_vega = sum(_dec(p.vega) for p in positions)

        # Strategy-level grouping from container positions
        real_strategies = _group_positions_into_strategies(
            positions, equity, buying_power,
        )

        # WhatIf trades from trade container
        whatif_trades = [
            _build_whatif_strategy_row(t, equity, buying_power)
            for t in whatif_trades_container
        ]

        # WhatIf position rows (leg-level)
        whatif_position_rows: List[Dict] = []
        for t in whatif_trades_container:
            whatif_position_rows.extend(_build_whatif_position_rows_from_container(t))

        # Risk factors from RiskFactorContainer (already aggregated by Steward)
        risk_factor_rows = _build_risk_factors_from_container(risk_factors)

        # Build spot lookup from real risk factors for WhatIf
        spot_by_udl = {r['underlying']: r['spot'] for r in risk_factor_rows if r.get('spot')}

        # WhatIf risk factors (aggregated from strategy-level data, with spots)
        whatif_risk_factor_rows = _build_whatif_risk_factors(whatif_trades, spot_by_udl)

        # WhatIf Greeks impact
        whatif_delta = sum(w['net_delta'] for w in whatif_trades)
        whatif_theta = sum(w['net_theta'] for w in whatif_trades)

        # VaR from portfolio container
        var_95 = float(pstate.var_1d_95)
        theta_var = abs(net_theta / var_95) if var_95 else 0

        # Market context from Scout's ResearchContainer
        market_context = {}
        research = cm.research
        for underlying in bundle.positions.underlyings:
            entry = research.get(underlying)
            if entry:
                market_context[underlying] = {
                    'regime': entry.regime_label,
                    'regime_id': entry.regime_id,
                    'phase': entry.phase_name,
                    'rsi': entry.rsi_14,
                    'iv_rank': entry.iv_rank,
                    'price': entry.current_price,
                    'atr': entry.atr,
                    'opp_zero_dte_verdict': entry.opp_zero_dte_verdict,
                    'opp_leap_verdict': entry.opp_leap_verdict,
                    'levels_direction': entry.levels_direction,
                    'levels_stop_price': entry.levels_stop_price,
                    'levels_best_target_price': entry.levels_best_target_price,
                }

        return {
            'portfolio': {
                'name': pstate.name,
                'portfolio_type': pstate.portfolio_type,
                'broker': bundle.broker_firm,
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
                'max_delta': float(pstate.max_delta),
                'delta_utilization_pct': round(
                    abs(net_delta) / float(pstate.max_delta) * 100, 1
                ) if float(pstate.max_delta) else 0,
                'open_positions': len(positions),
                'open_strategies': len(real_strategies),
                'whatif_count': len(whatif_trades),
            },
            'strategies': real_strategies,
            'positions': position_rows,
            'whatif_trades': whatif_trades,
            'whatif_positions': whatif_position_rows,
            'whatif_risk_factors': whatif_risk_factor_rows,
            'risk_factors': risk_factor_rows,
            'market_context': market_context,
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
        """Evaluate a research template against the portfolio.

        Uses ResearchContainer (Scout's data) instead of TechnicalAnalysisService.
        Portfolio state comes from containers (Steward's data).
        """
        try:
            from trading_cotrader.services.research.template_loader import load_research_templates
            from trading_cotrader.services.research.condition_evaluator import ConditionEvaluator
        except ImportError as e:
            raise HTTPException(500, f"Missing dependency: {e}")

        templates = load_research_templates()
        template = templates.get(body.template_name)
        if not template:
            raise HTTPException(404, f"Template '{body.template_name}' not found. Available: {list(templates.keys())}")

        # Portfolio state from containers
        cm = engine.container_manager
        if not cm:
            raise HTTPException(503, "Container manager not initialized")

        bundle = cm.get_bundle(portfolio_name)
        if not bundle or not bundle.portfolio.state:
            raise HTTPException(404, f"Portfolio bundle '{portfolio_name}' not found")

        # Use Scout's ResearchContainer + adapter for condition evaluation
        research = cm.research
        evaluator = ConditionEvaluator()
        global_ctx = {}
        if hasattr(engine, 'context'):
            global_ctx['vix'] = engine.context.get('vix', 20)

        evaluated = []
        triggered_count = 0

        for symbol in template.universe:
            entry = research.get(symbol)
            if not entry:
                evaluated.append({'symbol': symbol, 'triggered': False, 'conditions': {}, 'error': 'No research data'})
                continue

            # Use Scout's _ResearchEntryAdapter to bridge ResearchEntry -> ConditionEvaluator
            snapshot = engine.scout._make_snapshot_adapter(entry)

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
                    'price': float(entry.current_price) if entry.current_price else 0.0,
                    'rsi_14': entry.rsi_14,
                    'iv_rank': entry.iv_rank,
                },
            }

            if all_passed:
                triggered_count += 1

            evaluated.append(symbol_result)

        summary_parts = [f"{triggered_count} of {len(template.universe)} symbols triggered."]
        for ev in evaluated:
            if ev.get('triggered'):
                summary_parts.append(f"{ev['symbol']} triggered.")

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
        """Add a proposed trade to WhatIf.

        Constructs TastyTrade DXLink streamer symbols for each leg,
        fetches live Greeks and quotes from the broker, and stores
        them on the LegORM / TradeORM.
        """
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

            # --- Build legs and construct streamer symbols ---
            legs: List[LegORM] = []
            streamer_to_leg: Dict[str, LegORM] = {}
            streamer_symbols: List[str] = []

            for leg_data in body.legs:
                strike_val = leg_data.get('strike', 0)
                opt_type = leg_data.get('option_type', '')
                exp_str = leg_data.get('expiration', '')
                ticker_str = f"{body.underlying} {exp_str} {strike_val} {opt_type}".strip()
                strike_dec = Decimal(str(strike_val))
                exp_dt = datetime.fromisoformat(exp_str) if exp_str else None

                # Reuse existing symbol if one matches (unique constraint)
                symbol = session.query(SymbolORM).filter(
                    SymbolORM.ticker == ticker_str,
                    SymbolORM.asset_type == 'option',
                    SymbolORM.option_type == opt_type,
                    SymbolORM.strike == strike_dec,
                    SymbolORM.expiration == exp_dt,
                ).first()
                if not symbol:
                    symbol = SymbolORM(
                        id=str(uuid.uuid4()),
                        ticker=ticker_str,
                        asset_type='option',
                        option_type=opt_type,
                        strike=strike_dec,
                        expiration=exp_dt,
                    )
                    session.add(symbol)
                    session.flush()  # ensure symbol.id is assigned

                sym_id = symbol.id

                leg = LegORM(
                    id=str(uuid.uuid4()), trade_id=trade_id, symbol_id=sym_id,
                    quantity=leg_data.get('quantity', 0), side=leg_data.get('side', 'buy'),
                )
                session.add(leg)
                legs.append(leg)

                # Construct TastyTrade DXLink streamer symbol:
                # Format: .{TICKER}{YYMMDD}{C/P}{STRIKE_INT}
                if exp_str and strike_val and opt_type:
                    try:
                        exp_dt = datetime.fromisoformat(exp_str)
                        yymmdd = exp_dt.strftime('%y%m%d')
                        cp = 'C' if opt_type.lower() == 'call' else 'P'
                        strike_int = int(float(strike_val))
                        streamer_sym = f".{body.underlying}{yymmdd}{cp}{strike_int}"
                        streamer_symbols.append(streamer_sym)
                        streamer_to_leg[streamer_sym] = leg
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not build streamer symbol for leg: {e}")

            # --- Fetch live Greeks + quotes from TastyTrade DXLink ---
            broker_greeks: Dict = {}
            broker_quotes: Dict = {}
            adapter = engine._adapters.get('tastytrade') if hasattr(engine, '_adapters') else None

            if adapter and streamer_symbols:
                try:
                    logger.info(f"WhatIf: fetching Greeks for {streamer_symbols}")
                    broker_greeks = adapter.get_greeks(streamer_symbols)
                    logger.info(f"WhatIf: got Greeks for {len(broker_greeks)}/{len(streamer_symbols)} symbols")
                except Exception as e:
                    logger.warning(f"WhatIf Greeks fetch failed: {e}")

                try:
                    broker_quotes = adapter.get_quotes(streamer_symbols)
                    logger.info(f"WhatIf: got quotes for {len(broker_quotes)}/{len(streamer_symbols)} symbols")
                except Exception as e:
                    logger.warning(f"WhatIf quotes fetch failed: {e}")
            elif not adapter:
                logger.warning("WhatIf: no TastyTrade adapter available - Greeks will be 0")

            # --- Apply broker data to legs and aggregate ---
            total_delta = total_gamma = total_theta = total_vega = 0.0

            for streamer_sym, leg in streamer_to_leg.items():
                qty = leg.quantity or 0
                multiplier = 100  # standard option multiplier

                # Greeks from DXLink (per-contract, decimal form)
                greeks = broker_greeks.get(streamer_sym)
                if greeks:
                    # Per-contract Greeks from broker
                    per_delta = float(greeks.delta)
                    per_gamma = float(greeks.gamma)
                    per_theta = float(greeks.theta)
                    per_vega = float(greeks.vega)

                    # Position Greeks = per_contract * signed_qty * multiplier
                    pos_delta = per_delta * qty * multiplier
                    pos_gamma = per_gamma * abs(qty) * multiplier
                    pos_theta = per_theta * qty * multiplier
                    pos_vega = per_vega * qty * multiplier

                    leg.entry_delta = Decimal(str(round(pos_delta, 4)))
                    leg.entry_gamma = Decimal(str(round(pos_gamma, 6)))
                    leg.entry_theta = Decimal(str(round(pos_theta, 4)))
                    leg.entry_vega = Decimal(str(round(pos_vega, 4)))
                    leg.delta = leg.entry_delta
                    leg.gamma = leg.entry_gamma
                    leg.theta = leg.entry_theta
                    leg.vega = leg.entry_vega

                    total_delta += pos_delta
                    total_gamma += pos_gamma
                    total_theta += pos_theta
                    total_vega += pos_vega

                    logger.info(
                        f"  WhatIf leg {streamer_sym}: qty={qty}, "
                        f"per_contract_delta={per_delta:.4f}, pos_delta={pos_delta:.2f}"
                    )

                # Quote from DXLink (bid/ask -> mid for current price)
                quote = broker_quotes.get(streamer_sym)
                if quote:
                    bid = quote.get('bid', 0)
                    ask = quote.get('ask', 0)
                    mid = (bid + ask) / 2 if bid and ask else bid or ask
                    leg.entry_price = Decimal(str(round(mid, 4)))
                    leg.current_price = leg.entry_price
                    leg.entry_iv = None  # IV not in quote, comes from Greeks event

            trade.entry_delta = Decimal(str(round(total_delta, 4)))
            trade.entry_gamma = Decimal(str(round(total_gamma, 6)))
            trade.entry_theta = Decimal(str(round(total_theta, 4)))
            trade.entry_vega = Decimal(str(round(total_vega, 4)))
            trade.current_delta = trade.entry_delta
            trade.current_gamma = trade.entry_gamma
            trade.current_theta = trade.entry_theta
            trade.current_vega = trade.entry_vega

            # Compute entry_price as net credit/debit from leg quotes
            if body.entry_price is not None:
                trade.entry_price = Decimal(str(body.entry_price))
            else:
                net_premium = Decimal('0')
                for leg in legs:
                    if leg.entry_price and leg.quantity:
                        # Sell (negative qty) = credit, buy (positive qty) = debit
                        net_premium += (leg.entry_price or Decimal('0')) * leg.quantity
                    trade.entry_price = Decimal(str(round(float(net_premium), 4)))

            # max_risk from body (user-provided) — no mathematical approximation
            if body.max_risk is not None:
                trade.max_risk = Decimal(str(body.max_risk))

            session.add(trade)
            session.flush()

        # Refresh containers so WhatIf trade is reflected in-memory
        try:
            engine._refresh_containers()
        except Exception as e:
            logger.warning(f"Container refresh after add-whatif: {e}")

        return {'success': True, 'trade_id': trade_id}

    # -----------------------------------------------------------------------
    # DELETE /trading-dashboard/{portfolio_name}/whatif/{trade_id}
    # -----------------------------------------------------------------------
    @router.delete("/trading-dashboard/{portfolio_name}/whatif/{trade_id}")
    async def delete_whatif(portfolio_name: str, trade_id: str):
        """Delete a WhatIf trade."""
        with session_scope() as session:
            trade = session.query(TradeORM).get(trade_id)
            if not trade or trade.trade_type != 'what_if':
                raise HTTPException(404, "WhatIf trade not found")
            portfolio = session.query(PortfolioORM).get(trade.portfolio_id)
            if not portfolio or portfolio.name != portfolio_name:
                raise HTTPException(400, "Trade does not belong to this portfolio")
            session.delete(trade)

        # Refresh containers so deletion is reflected in-memory
        try:
            engine._refresh_containers()
        except Exception as e:
            logger.warning(f"Container refresh after delete-whatif: {e}")

        return {'status': 'deleted', 'trade_id': trade_id}

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

        # Refresh containers so booking is reflected in-memory
        try:
            engine._refresh_containers()
        except Exception as e:
            logger.warning(f"Container refresh after book-trade: {e}")

        return {'success': True, 'trade_id': body.whatif_trade_id}

    return router
