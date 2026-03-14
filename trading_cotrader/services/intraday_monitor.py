"""
Intraday Monitor — Fast-cycle monitoring for 0DTE desk positions (G13).

Runs every 2 minutes during market hours for desk_0dte positions.
Uses MA's IntradayService for real-time signal generation.

Signals: PROFIT_TARGET, STOP_LOSS, GAMMA_RISK, BREACH_SHORT_STRIKE,
         APPROACHING_STRIKE, MOMENTUM_SHIFT, VOLUME_SPIKE, VIX_SPIKE,
         TIME_DECAY_WINDOW, EXPIRY_APPROACHING

Called by:
  - Engine fast cycle (every 2 min, market hours only)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM

logger = logging.getLogger(__name__)

DESK_0DTE = 'desk_0dte'


@dataclass
class IntradayAction:
    """Action from intraday monitoring."""
    trade_id: str
    ticker: str
    signal_type: str
    urgency: str       # immediate, soon, monitor, info
    action: str        # CLOSE, MONITOR, ALERT
    message: str
    pnl_pct: Optional[float] = None


@dataclass
class IntradayResult:
    """Result of a fast monitoring cycle."""
    signals: List[IntradayAction] = field(default_factory=list)
    trades_checked: int = 0
    urgent_count: int = 0


class IntradayMonitorService:
    """Fast-cycle monitoring for 0DTE desk positions."""

    def __init__(self, ma):
        """
        Args:
            ma: MarketAnalyzer instance (needs intraday service + market_data).
        """
        self.ma = ma

    def run_fast_cycle(self) -> IntradayResult:
        """Run intraday monitoring on all open 0DTE positions.

        Returns IntradayResult with signals mapped to actions.
        """
        result = IntradayResult()

        try:
            from market_analyzer.service.intraday import IntradayService
        except ImportError:
            logger.debug("IntradayService not available")
            return result

        # Build position list for MA
        positions = self._get_0dte_positions()
        if not positions:
            return result

        result.trades_checked = len(positions)

        # Create IntradayService and monitor
        intraday = IntradayService(
            market_data=getattr(self.ma, '_market_data', None) if hasattr(self.ma, '_market_data') else None,
            market_metrics=getattr(self.ma, '_market_metrics', None) if hasattr(self.ma, '_market_metrics') else None,
            data_service=getattr(self.ma, '_data_service', None) if hasattr(self.ma, '_data_service') else None,
        )

        try:
            ma_result = intraday.monitor(positions)
        except Exception as e:
            logger.warning(f"IntradayService.monitor failed: {e}")
            return result

        # Map MA signals to IntradayActions
        for signal in ma_result.signals:
            urgency = signal.urgency.value if hasattr(signal.urgency, 'value') else str(signal.urgency)
            signal_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)

            # Determine action based on urgency
            if urgency == 'immediate':
                action = 'CLOSE'
            elif urgency == 'soon':
                action = 'ALERT'
            else:
                action = 'MONITOR'

            result.signals.append(IntradayAction(
                trade_id=signal.data.get('trade_id', ''),
                ticker=signal.ticker,
                signal_type=signal_type,
                urgency=urgency,
                action=action,
                message=signal.message,
                pnl_pct=signal.pnl_pct,
            ))

        result.urgent_count = sum(1 for s in result.signals if s.urgency == 'immediate')

        if result.signals:
            logger.info(
                f"Intraday: {len(result.signals)} signals "
                f"({result.urgent_count} immediate) "
                f"for {result.trades_checked} 0DTE positions"
            )

        return result

    def _get_0dte_positions(self) -> list:
        """Get open 0DTE positions formatted for MA's IntradayService."""
        positions = []
        today = date.today()

        with session_scope() as session:
            # Get open trades in 0DTE desk (or any 0-1 DTE trade)
            trades = session.query(TradeORM).filter(
                TradeORM.is_open == True,
            ).all()

            for trade in trades:
                # Check if any leg expires today (0DTE)
                is_0dte = False
                short_strikes = []

                for leg in trade.legs:
                    if not leg.symbol:
                        continue
                    exp = leg.symbol.expiration
                    if isinstance(exp, datetime):
                        exp = exp.date()
                    if exp and (exp - today).days <= 1:
                        is_0dte = True
                    # Collect short strikes
                    if leg.quantity and leg.quantity < 0 and leg.symbol.strike:
                        short_strikes.append(float(leg.symbol.strike))

                if not is_0dte or not short_strikes:
                    continue

                # Extract exit rules
                profit_target_pct = 0.90  # default for 0DTE
                stop_loss_multiple = None  # defined risk, no stop
                structure_type = 'unknown'

                if trade.strategy:
                    structure_type = trade.strategy.strategy_type or 'unknown'
                    if trade.strategy.profit_target_pct:
                        profit_target_pct = float(trade.strategy.profit_target_pct) / 100

                entry_credit = float(trade.entry_price or 0)

                positions.append({
                    'ticker': trade.underlying_symbol,
                    'short_strikes': short_strikes,
                    'entry_credit': abs(entry_credit),
                    'profit_target_pct': profit_target_pct,
                    'stop_loss_multiple': stop_loss_multiple,
                    'structure_type': structure_type,
                    'trade_id': trade.id,  # for signal mapping
                })

        return positions
