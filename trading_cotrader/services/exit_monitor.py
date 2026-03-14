"""
Exit Monitor — Delegates exit decisions to market_analyzer.

For each open trade:
  1. Converts TradeORM → TradeSpec via tradespec_bridge (G1)
  2. Calls MA's monitor_exit_conditions() for exit signals (G3)
  3. Maps MA's ExitMonitorResult → eTrading's ExitSignal format

MA decides close/hold/adjust. eTrading provides inputs and executes.
Falls back to local exit profile when MA is unavailable (no broker).

Called by:
  - Engine monitoring cycle (every 30 min)
  - CLI 'exits' command (on-demand)
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time as dt_time
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import re

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, LegORM, StrategyORM
from trading_cotrader.services.tradespec_bridge import trade_to_monitor_params

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    """A signal to exit or adjust a trade."""
    trade_id: str
    underlying: str
    strategy_type: str
    signal_type: str  # PROFIT_TARGET, STOP_LOSS, DTE_EXIT, EXPIRED, REGIME_CHANGE
    severity: str     # INFO, WARNING, URGENT
    current_pnl: Decimal
    current_pnl_pct: float
    message: str
    action: str       # CLOSE, REDUCE, ROLL, MONITOR

    # Context
    entry_price: Decimal = Decimal('0')
    current_price: Decimal = Decimal('0')
    dte: Optional[int] = None
    target_value: Optional[float] = None  # The threshold that triggered


@dataclass
class ExitMonitorResult:
    """Result of checking all trades for exit conditions."""
    signals: List[ExitSignal] = field(default_factory=list)
    trades_checked: int = 0
    trades_ok: int = 0

    @property
    def has_urgent(self) -> bool:
        return any(s.severity == 'URGENT' for s in self.signals)

    @property
    def urgent_count(self) -> int:
        return sum(1 for s in self.signals if s.severity == 'URGENT')

    @property
    def warning_count(self) -> int:
        return sum(1 for s in self.signals if s.severity == 'WARNING')


# ============================================================================
# Local exit profiles — fallback when MA is unavailable
# ============================================================================

def _get_exit_profile(strategy_type: str, order_side: str) -> Dict:
    """Return exit rule defaults by strategy type (offline fallback)."""
    zero_dte_types = {'iron_condor_0dte', 'iron_man_0dte', 'credit_spread_0dte',
                      'straddle_0dte', 'strangle_0dte'}
    defined_credit = {'iron_condor', 'iron_butterfly', 'credit_spread',
                      'vertical_spread', 'bull_put_spread', 'bear_call_spread'}
    defined_debit = {'debit_spread', 'bull_call_spread', 'bear_put_spread',
                     'long_option', 'long_call', 'long_put'}
    dual_expiry = {'calendar', 'double_calendar', 'diagonal', 'pmcc'}

    if strategy_type in zero_dte_types:
        return {'profit_target_pct': 0.90, 'stop_loss_pct': None, 'exit_dte': None}
    elif strategy_type in defined_credit:
        return {'profit_target_pct': 0.50, 'stop_loss_pct': 2.0, 'exit_dte': 21}
    elif strategy_type in defined_debit:
        return {'profit_target_pct': 1.0, 'stop_loss_pct': 0.50, 'exit_dte': 21}
    elif strategy_type in dual_expiry:
        return {'profit_target_pct': 0.25, 'stop_loss_pct': 0.50, 'exit_dte': None}
    elif 'leap' in strategy_type:
        return {'profit_target_pct': 1.0, 'stop_loss_pct': 0.50, 'exit_dte': 90}
    elif order_side == 'credit':
        return {'profit_target_pct': 0.50, 'stop_loss_pct': 2.0, 'exit_dte': 21}
    return {'profit_target_pct': 1.0, 'stop_loss_pct': 0.50, 'exit_dte': 21}


# ============================================================================
# MA urgency → eTrading severity mapping
# ============================================================================

_URGENCY_TO_SEVERITY = {
    'immediate': 'URGENT',
    'soon': 'WARNING',
    'monitor': 'INFO',
    'informational': 'INFO',
}

_RULE_TO_SIGNAL_TYPE = {
    'profit_target': 'PROFIT_TARGET',
    'stop_loss': 'STOP_LOSS',
    'dte_exit': 'DTE_EXIT',
    'expired': 'EXPIRED',
    'regime_change': 'REGIME_CHANGE',
    'time_of_day': 'DTE_EXIT',
}


class ExitMonitorService:
    """
    Monitor open trades for exit conditions.

    Primary path: delegates to MA's monitor_exit_conditions() (G3).
    Fallback path: local exit profile when MA unavailable.
    """

    def __init__(self, current_regime_id: int = 1):
        """
        Args:
            current_regime_id: Current market regime (R1-R4). Caller provides
                this from the latest regime detection. Default R1.
        """
        self._current_regime_id = current_regime_id

    def check_all_exits(self, trade_type: str = None) -> ExitMonitorResult:
        """
        Check all open trades for exit conditions.

        Tries MA's monitor_exit_conditions() first. Falls back to local
        logic if MA import fails or call errors.
        """
        result = ExitMonitorResult()

        with session_scope() as session:
            query = session.query(TradeORM).filter(TradeORM.is_open == True)
            if trade_type:
                query = query.filter(TradeORM.trade_type == trade_type)
            open_trades = query.all()

            result.trades_checked = len(open_trades)

            for trade in open_trades:
                signals = self._check_trade_via_ma(trade)
                if signals is None:
                    # MA unavailable, fall back to local
                    signals = self._check_trade_local(trade)
                if signals:
                    result.signals.extend(signals)
                else:
                    result.trades_ok += 1

        severity_order = {'URGENT': 0, 'WARNING': 1, 'INFO': 2}
        result.signals.sort(key=lambda s: severity_order.get(s.severity, 3))
        return result

    # ----------------------------------------------------------------
    # Primary path: MA-driven exit decisions (G3)
    # ----------------------------------------------------------------

    def _check_trade_via_ma(self, trade: TradeORM) -> Optional[List[ExitSignal]]:
        """Check exit conditions via MA's monitor_exit_conditions().

        Returns list of ExitSignal, or None if MA is unavailable.
        """
        try:
            from market_analyzer import monitor_exit_conditions
        except ImportError:
            return None

        params = trade_to_monitor_params(trade)
        if not params:
            return None

        # Override regime with current (caller's latest detection)
        params['regime_id'] = self._current_regime_id

        # Add time-of-day for EOD urgency escalation (G21)
        now = datetime.now()
        params['time_of_day'] = now.time()

        try:
            ma_result = monitor_exit_conditions(**params)
        except Exception as e:
            logger.warning(f"MA monitor_exit_conditions failed for {trade.id}: {e}")
            return None

        # Update health_status on trade (G4) based on MA result
        if ma_result.should_close:
            trade.health_status = 'exit_triggered'
        trade.health_checked_at = datetime.utcnow()

        # Map MA signals → eTrading ExitSignals
        signals = []
        for ma_signal in ma_result.signals:
            if not ma_signal.triggered:
                continue

            signal_type = _RULE_TO_SIGNAL_TYPE.get(ma_signal.rule, ma_signal.rule.upper())
            severity = _URGENCY_TO_SEVERITY.get(ma_signal.urgency, 'INFO')

            signals.append(ExitSignal(
                trade_id=trade.id,
                underlying=trade.underlying_symbol,
                strategy_type=params['structure_type'],
                signal_type=signal_type,
                severity=severity,
                current_pnl=Decimal(str(round(ma_result.pnl_dollars, 2))),
                current_pnl_pct=ma_result.pnl_pct,
                message=ma_signal.detail,
                action=ma_signal.action.upper() if ma_signal.action else 'CLOSE',
                entry_price=Decimal(str(params['entry_price'])),
                current_price=Decimal(str(params['current_mid_price'])),
                dte=params['dte_remaining'],
                target_value=(float(ma_signal.threshold)
                              if isinstance(ma_signal.threshold, (int, float)) else None),
            ))

        return signals

    # ----------------------------------------------------------------
    # Fallback path: local exit logic (offline mode)
    # ----------------------------------------------------------------

    def _check_trade_local(self, trade: TradeORM) -> List[ExitSignal]:
        """Check exit conditions using local logic (offline fallback)."""
        signals = []
        entry_price = Decimal(str(trade.entry_price or 0))
        current_price = Decimal(str(trade.current_price or 0))
        pnl = current_price - entry_price
        pnl_pct = float(pnl / abs(entry_price) * 100) if entry_price else 0

        strategy = trade.strategy
        strategy_type = strategy.strategy_type if strategy else 'unknown'
        dte = self._compute_dte(trade)
        rules = self._get_exit_rules(trade)
        profit_target_pct = rules.get('profit_target_pct')
        stop_loss_pct = rules.get('stop_loss_pct')
        exit_dte = rules.get('exit_dte')
        order_side = rules.get('order_side', 'credit')

        # Expired
        if dte is not None and dte <= 0:
            signals.append(ExitSignal(
                trade_id=trade.id, underlying=trade.underlying_symbol,
                strategy_type=strategy_type, signal_type='EXPIRED',
                severity='URGENT', current_pnl=pnl, current_pnl_pct=pnl_pct,
                message=f"{trade.underlying_symbol} {strategy_type} EXPIRED",
                action='CLOSE', entry_price=entry_price,
                current_price=current_price, dte=dte,
            ))
            return signals

        # DTE threshold
        if exit_dte is not None and dte is not None and dte <= exit_dte:
            signals.append(ExitSignal(
                trade_id=trade.id, underlying=trade.underlying_symbol,
                strategy_type=strategy_type, signal_type='DTE_EXIT',
                severity='WARNING', current_pnl=pnl, current_pnl_pct=pnl_pct,
                message=f"{trade.underlying_symbol} {strategy_type} — {dte} DTE (threshold: {exit_dte})",
                action='CLOSE', entry_price=entry_price,
                current_price=current_price, dte=dte, target_value=float(exit_dte),
            ))

        # Profit target
        if profit_target_pct is not None and entry_price:
            target_profit = abs(entry_price) * Decimal(str(profit_target_pct))
            if pnl >= target_profit and pnl > 0:
                signals.append(ExitSignal(
                    trade_id=trade.id, underlying=trade.underlying_symbol,
                    strategy_type=strategy_type, signal_type='PROFIT_TARGET',
                    severity='INFO', current_pnl=pnl, current_pnl_pct=pnl_pct,
                    message=f"{trade.underlying_symbol} {strategy_type} — P&L ${pnl:.2f} hit {profit_target_pct*100:.0f}% target",
                    action='CLOSE', entry_price=entry_price,
                    current_price=current_price, dte=dte, target_value=profit_target_pct,
                ))

        # Stop loss
        if stop_loss_pct is not None and entry_price and pnl < 0:
            max_loss = abs(entry_price) * Decimal(str(stop_loss_pct))
            if abs(pnl) >= max_loss:
                signals.append(ExitSignal(
                    trade_id=trade.id, underlying=trade.underlying_symbol,
                    strategy_type=strategy_type, signal_type='STOP_LOSS',
                    severity='URGENT', current_pnl=pnl, current_pnl_pct=pnl_pct,
                    message=f"{trade.underlying_symbol} {strategy_type} — STOP LOSS ${pnl:.2f}",
                    action='CLOSE', entry_price=entry_price,
                    current_price=current_price, dte=dte, target_value=stop_loss_pct,
                ))

        return signals

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _compute_dte(self, trade: TradeORM) -> Optional[int]:
        """Compute days to earliest leg expiration."""
        today = date.today()
        dtes = []
        for leg in trade.legs:
            if leg.symbol and leg.symbol.expiration:
                exp = leg.symbol.expiration
                if isinstance(exp, datetime):
                    exp = exp.date()
                dtes.append((exp - today).days)
        return min(dtes) if dtes else None

    def _get_exit_rules(self, trade: TradeORM) -> Dict:
        """Extract exit rules (fallback path only)."""
        rules = {}
        strategy = trade.strategy
        if strategy:
            if strategy.profit_target_pct is not None:
                rules['profit_target_pct'] = float(strategy.profit_target_pct) / 100
            if hasattr(strategy, 'stop_loss_pct') and strategy.stop_loss_pct is not None:
                rules['stop_loss_pct'] = float(strategy.stop_loss_pct) / 100
            if hasattr(strategy, 'dte_exit') and strategy.dte_exit is not None:
                rules['exit_dte'] = int(strategy.dte_exit)

        notes = trade.notes or ''
        if 'Exit:' in notes or 'exit:' in notes:
            parsed = self._parse_exit_notes(notes)
            rules.update(parsed)

        if 'order_side' not in rules:
            entry = Decimal(str(trade.entry_price or 0))
            rules['order_side'] = 'credit' if entry > 0 else 'debit'

        strategy_type = (strategy.strategy_type if strategy else '').lower()
        profile = _get_exit_profile(strategy_type, rules.get('order_side', 'credit'))

        if 'profit_target_pct' not in rules:
            rules['profit_target_pct'] = profile['profit_target_pct']
        if 'stop_loss_pct' not in rules:
            rules['stop_loss_pct'] = profile['stop_loss_pct']
        if 'exit_dte' not in rules:
            rules['exit_dte'] = profile['exit_dte']

        return rules

    def _parse_exit_notes(self, notes: str) -> Dict:
        """Parse exit rules from trade notes text."""
        rules = {}
        tp_match = re.search(r'TP\s+(\d+)%', notes, re.IGNORECASE)
        if tp_match:
            rules['profit_target_pct'] = int(tp_match.group(1)) / 100
        sl_match = re.search(r'SL\s+(\d+(?:\.\d+)?)\s*[×x]', notes, re.IGNORECASE)
        if sl_match:
            rules['stop_loss_pct'] = float(sl_match.group(1))
        else:
            sl_pct_match = re.search(r'SL\s+(\d+)%', notes, re.IGNORECASE)
            if sl_pct_match:
                rules['stop_loss_pct'] = int(sl_pct_match.group(1)) / 100
        dte_match = re.search(r'(?:close|exit)\s*(?:≤|<=|by)?\s*(\d+)\s*DTE', notes, re.IGNORECASE)
        if dte_match:
            rules['exit_dte'] = int(dte_match.group(1))
        if 'credit' in notes.lower():
            rules['order_side'] = 'credit'
        elif 'debit' in notes.lower():
            rules['order_side'] = 'debit'
        return rules
