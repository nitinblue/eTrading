"""
TradeSpec Bridge — converts between eTrading DB models and MA TradeSpec.

This is the critical bridge (G1) that enables all MA monitoring APIs.
MA's trade_lifecycle functions (monitor_exit_conditions, check_trade_health,
compute_breakevens, estimate_pop, etc.) all require TradeSpec as input.
eTrading stores trades as TradeORM + LegORM + SymbolORM in SQLite.

Direction 1 (eTrading → MA): trade_to_tradespec()
  TradeORM → extract DXLink symbols + actions → from_dxlink_symbols() → TradeSpec

Direction 2 (MA → eTrading): Already handled by Maverick._trade_spec_to_leg_inputs()
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from market_analyzer import from_dxlink_symbols, TradeSpec, MarketRegistry

from trading_cotrader.core.database.schema import TradeORM, LegORM, SymbolORM

logger = logging.getLogger(__name__)

# Cache registry instance
_registry = None

def get_registry() -> MarketRegistry:
    """Get cached MarketRegistry instance."""
    global _registry
    if _registry is None:
        _registry = MarketRegistry()
    return _registry


def get_lot_size(ticker: str, market: str = 'US') -> int:
    """Get lot size for a ticker from MarketRegistry. Default 100."""
    try:
        registry = get_registry()
        inst = registry.get_instrument(ticker, market=market)
        return inst.lot_size
    except Exception:
        return 100


def _symbol_to_dxlink(symbol: SymbolORM) -> Optional[str]:
    """Convert a SymbolORM to DXLink streamer symbol format.

    Returns:
        ".SPY260320P550" for options, None for non-options or missing data.
    """
    if not symbol or symbol.asset_type != 'option':
        return None
    if not all([symbol.ticker, symbol.expiration, symbol.option_type, symbol.strike]):
        logger.warning(f"Incomplete symbol data for {symbol.id}: "
                       f"ticker={symbol.ticker}, exp={symbol.expiration}, "
                       f"type={symbol.option_type}, strike={symbol.strike}")
        return None

    exp = symbol.expiration
    if isinstance(exp, datetime):
        exp = exp.date()
    opt_char = 'C' if symbol.option_type == 'call' else 'P'
    date_part = exp.strftime('%y%m%d')
    strike_int = int(symbol.strike)
    return f".{symbol.ticker}{date_part}{opt_char}{strike_int}"


def _leg_action(leg: LegORM) -> str:
    """Determine BTO/STO from leg quantity or side field."""
    if leg.quantity is not None and leg.quantity < 0:
        return "STO"
    if leg.side and leg.side.upper() in ('SELL', 'STO', 'SELL_TO_OPEN'):
        return "STO"
    return "BTO"


def trade_to_tradespec(
    trade: TradeORM,
    underlying_price: Optional[float] = None,
) -> Optional[TradeSpec]:
    """Convert a TradeORM (with loaded legs + symbols) to MA TradeSpec.

    Args:
        trade: TradeORM with legs relationship loaded (each leg must have
               symbol relationship loaded).
        underlying_price: Current underlying price. Falls back to
                         trade.current_underlying_price or entry_underlying_price.

    Returns:
        TradeSpec ready for MA APIs, or None if conversion fails.
    """
    if not trade.legs:
        logger.warning(f"Trade {trade.id} has no legs, cannot build TradeSpec")
        return None

    # Collect DXLink symbols and actions from legs
    symbols = []
    actions = []
    quantities = []

    for leg in trade.legs:
        if not leg.symbol:
            logger.warning(f"Leg {leg.id} on trade {trade.id} has no symbol loaded")
            continue

        dxlink = _symbol_to_dxlink(leg.symbol)
        if not dxlink:
            logger.warning(f"Cannot build DXLink symbol for leg {leg.id}")
            continue

        symbols.append(dxlink)
        actions.append(_leg_action(leg))
        quantities.append(abs(leg.quantity))

    if not symbols:
        logger.warning(f"Trade {trade.id}: no valid option legs for TradeSpec")
        return None

    # Determine underlying price
    price = underlying_price
    if price is None and trade.current_underlying_price:
        price = float(trade.current_underlying_price)
    if price is None and trade.entry_underlying_price:
        price = float(trade.entry_underlying_price)
    if price is None:
        logger.warning(f"Trade {trade.id}: no underlying price available, using 0")
        price = 0.0

    # Extract exit rules from strategy or trade fields
    profit_target_pct = None
    stop_loss_pct = None
    exit_dte = None

    if trade.strategy:
        if trade.strategy.profit_target_pct:
            profit_target_pct = float(trade.strategy.profit_target_pct) / 100.0
        if trade.strategy.stop_loss_pct:
            stop_loss_pct = float(trade.strategy.stop_loss_pct) / 100.0
        if trade.strategy.dte_exit:
            exit_dte = trade.strategy.dte_exit

    # Get entry price
    entry_price = None
    if trade.entry_price:
        entry_price = float(trade.entry_price)

    # Determine structure type from strategy
    structure_type = None
    if trade.strategy and trade.strategy.strategy_type:
        structure_type = trade.strategy.strategy_type

    try:
        spec = from_dxlink_symbols(
            symbols=symbols,
            actions=actions,
            underlying_price=price,
            structure_type=structure_type,
            quantities=quantities if any(q != 1 for q in quantities) else None,
            entry_price=entry_price,
            profit_target_pct=profit_target_pct,
            stop_loss_pct=stop_loss_pct,
            exit_dte=exit_dte,
        )
        return spec
    except Exception as e:
        logger.error(f"Trade {trade.id}: from_dxlink_symbols failed: {e}")
        return None


def trade_to_dxlink_symbols(trade: TradeORM) -> list[str]:
    """Extract DXLink symbols from a trade's legs.

    Useful for subscribing to streamer quotes for mark-to-market.
    """
    symbols = []
    for leg in (trade.legs or []):
        if leg.symbol:
            dxlink = _symbol_to_dxlink(leg.symbol)
            if dxlink:
                symbols.append(dxlink)
    return symbols


def trade_to_monitor_params(trade: TradeORM) -> Optional[dict]:
    """Extract parameters needed to call MA's monitor_exit_conditions().

    Returns a dict with all params ready to unpack into the call, or None.
    """
    if not trade.legs or not trade.entry_price:
        return None

    # Determine structure_type and order_side
    structure_type = None
    if trade.strategy and trade.strategy.strategy_type:
        structure_type = trade.strategy.strategy_type

    order_side = 'credit' if trade.entry_price and float(trade.entry_price) > 0 else 'debit'

    # Calculate DTE from first leg's expiration
    dte_remaining = None
    for leg in trade.legs:
        if leg.symbol and leg.symbol.expiration:
            exp = leg.symbol.expiration
            if isinstance(exp, datetime):
                exp = exp.date()
            dte_remaining = (exp - date.today()).days
            break

    if dte_remaining is None:
        return None

    # Exit rules
    profit_target_pct = 0.50  # default
    stop_loss_pct = 2.0       # default
    exit_dte = 21             # default

    if trade.strategy:
        if trade.strategy.profit_target_pct:
            profit_target_pct = float(trade.strategy.profit_target_pct) / 100.0
        if trade.strategy.stop_loss_pct:
            stop_loss_pct = float(trade.strategy.stop_loss_pct) / 100.0
        if trade.strategy.dte_exit:
            exit_dte = trade.strategy.dte_exit

    # Regime at entry
    entry_regime_id = None
    if trade.regime_at_entry:
        try:
            entry_regime_id = int(trade.regime_at_entry.replace('R', ''))
        except (ValueError, AttributeError):
            pass

    contracts = 1
    if trade.legs:
        contracts = max(abs(leg.quantity) for leg in trade.legs if leg.quantity)

    return {
        'trade_id': trade.id,
        'ticker': trade.underlying_symbol,
        'structure_type': structure_type or 'unknown',
        'order_side': order_side,
        'entry_price': float(trade.entry_price),
        'current_mid_price': float(trade.current_price) if trade.current_price else 0.0,
        'contracts': contracts,
        'dte_remaining': dte_remaining,
        'regime_id': 1,  # will be overridden by caller with current regime
        'profit_target_pct': profit_target_pct,
        'stop_loss_pct': stop_loss_pct,
        'exit_dte': exit_dte,
        'entry_regime_id': entry_regime_id,
        'lot_size': get_lot_size(trade.underlying_symbol),  # E11: India lots differ
    }
