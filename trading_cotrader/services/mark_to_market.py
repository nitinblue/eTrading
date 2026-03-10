"""
Mark-to-Market Service — Keep trades alive with real prices.

Updates open WhatIf (and real) trades with current market data:
  1. Fetch current quotes (bid/ask) for all leg symbols via broker DXLink
  2. Fetch current Greeks for option legs
  3. Update LegORM and TradeORM current_price + current Greeks
  4. Compute trade-level P&L
  5. Refresh containers for UI

Called by:
  - Engine monitoring cycle (every 30 min)
  - CLI 'mark' command (on-demand)
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
import re

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, LegORM, SymbolORM

logger = logging.getLogger(__name__)

# Parse DXLink streamer symbol from leg's SymbolORM
_OPTION_SYMBOL_RE = re.compile(r'^\.([A-Z]+)(\d{6})([PC])(\d+)$')


@dataclass
class MarkResult:
    """Result of marking a single trade."""
    trade_id: str
    underlying: str
    strategy_type: str
    entry_price: Decimal
    current_price: Decimal
    pnl: Decimal
    pnl_pct: float
    legs_marked: int
    legs_total: int


@dataclass
class MarkToMarketResult:
    """Result of a full mark-to-market run."""
    trades_marked: int = 0
    trades_failed: int = 0
    trades_skipped: int = 0
    results: List[MarkResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_pnl(self) -> Decimal:
        return sum(r.pnl for r in self.results)


def _build_streamer_symbol(symbol_orm: SymbolORM) -> Optional[str]:
    """Build DXLink streamer symbol from SymbolORM."""
    if not symbol_orm:
        return None

    if symbol_orm.asset_type == 'equity':
        return symbol_orm.ticker

    # Option: .TICKER YYMMDD P/C STRIKE
    if symbol_orm.expiration and symbol_orm.strike is not None:
        opt_char = 'C' if (symbol_orm.option_type or '').lower() in ('call', 'c') else 'P'
        date_part = symbol_orm.expiration.strftime('%y%m%d')
        strike_int = int(symbol_orm.strike)
        return f".{symbol_orm.ticker}{date_part}{opt_char}{strike_int}"

    return None


class MarkToMarketService:
    """
    Fetch live prices and Greeks for open trades, update DB.

    Usage:
        service = MarkToMarketService(broker)
        result = service.mark_all_open_trades()
        print(f"Marked {result.trades_marked} trades, total P&L: ${result.total_pnl:.2f}")
    """

    def __init__(self, broker, container_manager=None):
        self.broker = broker
        self.container_manager = container_manager

    def mark_all_open_trades(self, trade_type: str = None) -> MarkToMarketResult:
        """
        Mark all open trades to current market prices.

        Args:
            trade_type: Filter to 'what_if', 'real', etc. None = all open trades.

        Returns:
            MarkToMarketResult with per-trade results and aggregate P&L.
        """
        result = MarkToMarketResult()

        with session_scope() as session:
            # Get all open trades
            query = session.query(TradeORM).filter(TradeORM.is_open == True)
            if trade_type:
                query = query.filter(TradeORM.trade_type == trade_type)
            open_trades = query.all()

            if not open_trades:
                logger.info("No open trades to mark")
                return result

            logger.info(f"Marking {len(open_trades)} open trades to market")

            # Collect all streamer symbols across all trades
            symbol_map: Dict[str, List[Tuple[TradeORM, LegORM, SymbolORM]]] = {}
            for trade in open_trades:
                for leg in trade.legs:
                    sym = _build_streamer_symbol(leg.symbol)
                    if sym:
                        symbol_map.setdefault(sym, []).append((trade, leg, leg.symbol))

            if not symbol_map:
                logger.warning("No valid symbols to fetch quotes for")
                result.trades_skipped = len(open_trades)
                return result

            # Fetch quotes and Greeks in bulk
            all_symbols = list(symbol_map.keys())
            option_symbols = [s for s in all_symbols if s.startswith('.')]
            equity_symbols = [s for s in all_symbols if not s.startswith('.')]

            quotes_map = self._fetch_quotes(all_symbols)
            greeks_map = self._fetch_greeks(option_symbols) if option_symbols else {}

            logger.info(
                f"Fetched quotes for {len(quotes_map)}/{len(all_symbols)} symbols, "
                f"Greeks for {len(greeks_map)}/{len(option_symbols)} options"
            )

            # Update each leg
            updated_legs = set()
            for sym, entries in symbol_map.items():
                quote = quotes_map.get(sym, {})
                greeks = greeks_map.get(sym)
                bid = quote.get('bid', 0) or 0
                ask = quote.get('ask', 0) or 0
                mid = (bid + ask) / 2 if (bid and ask) else 0

                if not mid:
                    continue

                for trade, leg, symbol_orm in entries:
                    leg.current_price = Decimal(str(round(mid, 4)))
                    if greeks:
                        leg.delta = getattr(greeks, 'delta', leg.delta)
                        leg.gamma = getattr(greeks, 'gamma', leg.gamma)
                        leg.theta = getattr(greeks, 'theta', leg.theta)
                        leg.vega = getattr(greeks, 'vega', leg.vega)
                    updated_legs.add(leg.id)

            # Now update trade-level aggregates
            for trade in open_trades:
                try:
                    trade_result = self._update_trade_aggregates(trade)
                    if trade_result:
                        result.results.append(trade_result)
                        result.trades_marked += 1
                    else:
                        result.trades_skipped += 1
                except Exception as e:
                    result.trades_failed += 1
                    result.errors.append(f"{trade.underlying_symbol}: {e}")
                    logger.error(f"Error marking trade {trade.id}: {e}")

            # Commit all updates
            session.commit()

        # Refresh containers
        if self.container_manager:
            try:
                with session_scope() as session:
                    self.container_manager.load_from_repositories(session)
                logger.info("Containers refreshed after mark-to-market")
            except Exception as e:
                logger.warning(f"Container refresh failed: {e}")

        logger.info(
            f"Mark-to-market complete: {result.trades_marked} marked, "
            f"{result.trades_failed} failed, total P&L=${result.total_pnl:.2f}"
        )
        return result

    def _update_trade_aggregates(self, trade: TradeORM) -> Optional[MarkResult]:
        """Recompute trade-level price and Greeks from its legs."""
        if not trade.legs:
            return None

        net_current = Decimal('0')
        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')
        legs_marked = 0

        for leg in trade.legs:
            qty = leg.quantity or 0
            multiplier = 100  # options
            if leg.symbol and leg.symbol.asset_type == 'equity':
                multiplier = 1

            current = Decimal(str(leg.current_price or 0))
            entry = Decimal(str(leg.entry_price or 0))
            is_short = qty < 0

            if current > 0:
                legs_marked += 1

            # Net current price: credit (short) positive, debit (long) negative
            leg_value = current * abs(qty) * multiplier
            net_current += leg_value if is_short else -leg_value

            # Position Greeks
            delta = Decimal(str(leg.delta or 0))
            gamma = Decimal(str(leg.gamma or 0))
            theta = Decimal(str(leg.theta or 0))
            vega = Decimal(str(leg.vega or 0))

            total_delta += delta * qty * multiplier
            total_gamma += gamma * abs(qty) * multiplier
            total_theta += theta * qty * multiplier
            total_vega += vega * qty * multiplier

        # Update trade
        entry_price = Decimal(str(trade.entry_price or 0))
        trade.current_price = net_current
        trade.current_delta = total_delta
        trade.current_gamma = total_gamma
        trade.current_theta = total_theta
        trade.current_vega = total_vega

        # P&L = current_value - entry_value (for credit trades, entry is positive)
        pnl = entry_price - net_current  # If credit trade: entry=+credit, current=-cost_to_close
        # Actually: P&L for credit = credit_received - cost_to_close
        # entry_price is net credit (positive), current_price should be cost to close (negative)
        # So pnl = entry_price + current_price when using same sign convention
        # Simpler: pnl = entry_price - abs(current net value change)
        # Let's use the standard: pnl = current net - entry net (both in same convention)
        pnl = net_current - entry_price
        trade.total_pnl = pnl
        trade.last_updated = datetime.utcnow()

        pnl_pct = float(pnl / abs(entry_price) * 100) if entry_price else 0

        strategy = trade.strategy.strategy_type if trade.strategy else trade.trade_type
        return MarkResult(
            trade_id=trade.id,
            underlying=trade.underlying_symbol,
            strategy_type=strategy,
            entry_price=entry_price,
            current_price=net_current,
            pnl=pnl,
            pnl_pct=pnl_pct,
            legs_marked=legs_marked,
            legs_total=len(trade.legs),
        )

    def _fetch_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch bid/ask quotes via broker."""
        if not self.broker:
            logger.info("No broker — cannot fetch quotes")
            return {}
        try:
            return self.broker.get_quotes(symbols)
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")
            return {}

    def _fetch_greeks(self, option_symbols: List[str]) -> Dict:
        """Fetch Greeks for option symbols via DXLink."""
        if not self.broker or not option_symbols:
            return {}
        try:
            return self.broker._run_async(
                self.broker._fetch_greeks_via_dxlink(option_symbols)
            )
        except Exception as e:
            logger.error(f"Failed to fetch Greeks: {e}")
            return {}
