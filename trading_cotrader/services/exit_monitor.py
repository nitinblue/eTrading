"""
Exit Monitor — Watches open trades against their exit rules.

For each open trade, checks:
  1. Profit target hit (e.g., 50% of max profit)
  2. Stop loss hit (e.g., 2× credit received)
  3. DTE threshold (e.g., close by 21 DTE to avoid gamma risk)
  4. Expired (DTE <= 0)

Exit rules come from:
  - TradeORM.profit_target (dollar value) / TradeORM.stop_loss (dollar value)
  - StrategyORM.profit_target_pct / stop_loss_pct / dte_exit
  - Trade notes (parsed exit summary from TradeSpec)

Called by:
  - Engine monitoring cycle (every 30 min)
  - CLI 'exits' command (on-demand)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import re

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, LegORM, StrategyORM

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    """A signal to exit or adjust a trade."""
    trade_id: str
    underlying: str
    strategy_type: str
    signal_type: str  # PROFIT_TARGET, STOP_LOSS, DTE_EXIT, EXPIRED
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


def _get_exit_profile(strategy_type: str, order_side: str) -> Dict:
    """
    Return exit rule defaults by strategy type.

    Two categories:
      1. DEFINED-RISK / 0DTE: Risk is capped by structure (wing width).
         No stop loss needed — let expiration be the stop. High profit target.
      2. STANDARD: Both profit target and stop loss defined.

    These are defaults — TradeSpec exit rules from market_analyzer override these.
    Exit orders are triggered by our system, not resting OCO orders on broker.
    """
    # 0DTE strategies: defined risk, no stop loss, high profit target
    zero_dte_types = {'iron_condor_0dte', 'iron_man_0dte', 'credit_spread_0dte',
                      'straddle_0dte', 'strangle_0dte'}

    # Defined-risk credit structures: let them expire or take profit
    defined_credit = {'iron_condor', 'iron_butterfly', 'credit_spread',
                      'vertical_spread', 'bull_put_spread', 'bear_call_spread'}

    # Defined-risk debit structures: profit target + loss limit
    defined_debit = {'debit_spread', 'bull_call_spread', 'bear_put_spread',
                     'long_option', 'long_call', 'long_put'}

    # Dual-expiry structures
    dual_expiry = {'calendar', 'double_calendar', 'diagonal', 'pmcc'}

    if strategy_type in zero_dte_types:
        return {
            'profit_target_pct': 0.90,  # Take profit at 90% of credit
            'stop_loss_pct': None,       # No stop — risk defined by wings
            'exit_dte': None,            # Expires same day
        }
    elif strategy_type in defined_credit:
        return {
            'profit_target_pct': 0.50,  # Standard: 50% of credit
            'stop_loss_pct': 2.0,       # 2× credit received
            'exit_dte': 21,             # Close by 21 DTE
        }
    elif strategy_type in defined_debit:
        return {
            'profit_target_pct': 1.0,   # 100% return on debit
            'stop_loss_pct': 0.50,      # Cut at 50% loss
            'exit_dte': 21,
        }
    elif strategy_type in dual_expiry:
        return {
            'profit_target_pct': 0.25,  # 25% of max (calendars have modest targets)
            'stop_loss_pct': 0.50,      # 50% of debit
            'exit_dte': None,           # Close before front expiry (handled separately)
        }
    elif 'leap' in strategy_type:
        return {
            'profit_target_pct': 1.0,   # 100% return
            'stop_loss_pct': 0.50,      # 50% loss limit
            'exit_dte': 90,             # Roll at 90 DTE
        }
    else:
        # Generic fallback
        if order_side == 'credit':
            return {
                'profit_target_pct': 0.50,
                'stop_loss_pct': 2.0,
                'exit_dte': 21,
            }
        return {
            'profit_target_pct': 1.0,
            'stop_loss_pct': 0.50,
            'exit_dte': 21,
        }


class ExitMonitorService:
    """
    Monitor open trades for exit conditions.

    Usage:
        monitor = ExitMonitorService()
        result = monitor.check_all_exits()
        for signal in result.signals:
            print(f"{signal.severity}: {signal.message}")
    """

    def check_all_exits(self, trade_type: str = None) -> ExitMonitorResult:
        """
        Check all open trades for exit conditions.

        Args:
            trade_type: Filter to 'what_if', 'real', etc. None = all.

        Returns:
            ExitMonitorResult with signals for trades needing attention.
        """
        result = ExitMonitorResult()

        with session_scope() as session:
            query = session.query(TradeORM).filter(TradeORM.is_open == True)
            if trade_type:
                query = query.filter(TradeORM.trade_type == trade_type)
            open_trades = query.all()

            result.trades_checked = len(open_trades)

            for trade in open_trades:
                signals = self._check_trade(trade)
                if signals:
                    result.signals.extend(signals)
                else:
                    result.trades_ok += 1

        # Sort: URGENT first, then WARNING, then INFO
        severity_order = {'URGENT': 0, 'WARNING': 1, 'INFO': 2}
        result.signals.sort(key=lambda s: severity_order.get(s.severity, 3))

        return result

    def _check_trade(self, trade: TradeORM) -> List[ExitSignal]:
        """Check a single trade for exit conditions."""
        signals = []
        entry_price = Decimal(str(trade.entry_price or 0))
        current_price = Decimal(str(trade.current_price or 0))

        # P&L (same convention as mark_to_market)
        pnl = current_price - entry_price
        pnl_pct = float(pnl / abs(entry_price) * 100) if entry_price else 0

        strategy = trade.strategy
        strategy_type = strategy.strategy_type if strategy else 'unknown'

        # Compute DTE from leg expirations
        dte = self._compute_dte(trade)

        # Get exit rules
        rules = self._get_exit_rules(trade)
        profit_target_pct = rules.get('profit_target_pct')
        stop_loss_pct = rules.get('stop_loss_pct')
        exit_dte = rules.get('exit_dte')
        order_side = rules.get('order_side', 'credit')

        # Check 1: Expired
        if dte is not None and dte <= 0:
            signals.append(ExitSignal(
                trade_id=trade.id,
                underlying=trade.underlying_symbol,
                strategy_type=strategy_type,
                signal_type='EXPIRED',
                severity='URGENT',
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                message=f"{trade.underlying_symbol} {strategy_type} EXPIRED — close immediately",
                action='CLOSE',
                entry_price=entry_price,
                current_price=current_price,
                dte=dte,
            ))
            return signals  # Don't check other conditions if expired

        # Check 2: DTE threshold (skip if exit_dte is None — e.g., 0DTE holds to expiry)
        if exit_dte is not None and dte is not None and dte <= exit_dte:
            signals.append(ExitSignal(
                trade_id=trade.id,
                underlying=trade.underlying_symbol,
                strategy_type=strategy_type,
                signal_type='DTE_EXIT',
                severity='WARNING',
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                message=(
                    f"{trade.underlying_symbol} {strategy_type} — "
                    f"{dte} DTE (exit threshold: {exit_dte})"
                ),
                action='CLOSE',
                entry_price=entry_price,
                current_price=current_price,
                dte=dte,
                target_value=float(exit_dte),
            ))

        # Check 3: Profit target
        if profit_target_pct is not None and entry_price:
            # For credit trades: max profit = credit received (entry_price)
            # For debit trades: max profit is width - debit (unknown here, use entry as base)
            if order_side == 'credit':
                max_profit = abs(entry_price)
                target_profit = max_profit * Decimal(str(profit_target_pct))
                if pnl >= target_profit and pnl > 0:
                    signals.append(ExitSignal(
                        trade_id=trade.id,
                        underlying=trade.underlying_symbol,
                        strategy_type=strategy_type,
                        signal_type='PROFIT_TARGET',
                        severity='INFO',
                        current_pnl=pnl,
                        current_pnl_pct=pnl_pct,
                        message=(
                            f"{trade.underlying_symbol} {strategy_type} — "
                            f"P&L ${pnl:.2f} ({pnl_pct:.0f}%) hit "
                            f"{profit_target_pct*100:.0f}% profit target"
                        ),
                        action='CLOSE',
                        entry_price=entry_price,
                        current_price=current_price,
                        dte=dte,
                        target_value=profit_target_pct,
                    ))
            else:
                # Debit trade: profit = current - entry
                # profit_target_pct is fraction of max (e.g., 1.0 = 100% return)
                target_profit = abs(entry_price) * Decimal(str(profit_target_pct))
                if pnl >= target_profit and pnl > 0:
                    signals.append(ExitSignal(
                        trade_id=trade.id,
                        underlying=trade.underlying_symbol,
                        strategy_type=strategy_type,
                        signal_type='PROFIT_TARGET',
                        severity='INFO',
                        current_pnl=pnl,
                        current_pnl_pct=pnl_pct,
                        message=(
                            f"{trade.underlying_symbol} {strategy_type} — "
                            f"P&L ${pnl:.2f} ({pnl_pct:.0f}%) hit profit target"
                        ),
                        action='CLOSE',
                        entry_price=entry_price,
                        current_price=current_price,
                        dte=dte,
                        target_value=profit_target_pct,
                    ))

        # Check 4: Stop loss
        if stop_loss_pct is not None and entry_price and pnl < 0:
            if order_side == 'credit':
                # Credit trade: stop_loss_pct is multiple of credit received
                # e.g., 2.0 means stop when loss = 2× credit
                max_loss = abs(entry_price) * Decimal(str(stop_loss_pct))
                if abs(pnl) >= max_loss:
                    signals.append(ExitSignal(
                        trade_id=trade.id,
                        underlying=trade.underlying_symbol,
                        strategy_type=strategy_type,
                        signal_type='STOP_LOSS',
                        severity='URGENT',
                        current_pnl=pnl,
                        current_pnl_pct=pnl_pct,
                        message=(
                            f"{trade.underlying_symbol} {strategy_type} — "
                            f"STOP LOSS: ${pnl:.2f} ({pnl_pct:.0f}%) exceeds "
                            f"{stop_loss_pct}× credit"
                        ),
                        action='CLOSE',
                        entry_price=entry_price,
                        current_price=current_price,
                        dte=dte,
                        target_value=stop_loss_pct,
                    ))
            else:
                # Debit trade: stop_loss_pct is fraction of debit to lose
                # e.g., 0.50 means stop when loss = 50% of debit paid
                max_loss = abs(entry_price) * Decimal(str(stop_loss_pct))
                if abs(pnl) >= max_loss:
                    signals.append(ExitSignal(
                        trade_id=trade.id,
                        underlying=trade.underlying_symbol,
                        strategy_type=strategy_type,
                        signal_type='STOP_LOSS',
                        severity='URGENT',
                        current_pnl=pnl,
                        current_pnl_pct=pnl_pct,
                        message=(
                            f"{trade.underlying_symbol} {strategy_type} — "
                            f"STOP LOSS: ${pnl:.2f} ({pnl_pct:.0f}%) exceeds "
                            f"{stop_loss_pct*100:.0f}% loss limit"
                        ),
                        action='CLOSE',
                        entry_price=entry_price,
                        current_price=current_price,
                        dte=dte,
                        target_value=stop_loss_pct,
                    ))

        return signals

    def _compute_dte(self, trade: TradeORM) -> Optional[int]:
        """Compute days to earliest leg expiration."""
        today = date.today()
        dtes = []
        for leg in trade.legs:
            if leg.symbol and leg.symbol.expiration:
                exp = leg.symbol.expiration
                if isinstance(exp, datetime):
                    exp = exp.date()
                dte = (exp - today).days
                dtes.append(dte)
        return min(dtes) if dtes else None

    def _get_exit_rules(self, trade: TradeORM) -> Dict:
        """
        Extract exit rules from trade strategy and notes.

        Priority:
          1. StrategyORM fields (profit_target_pct, stop_loss_pct, dte_exit)
          2. Parsed from trade notes (exit summary from TradeSpec)
          3. Conservative defaults
        """
        rules = {}

        # From strategy
        strategy = trade.strategy
        if strategy:
            if strategy.profit_target_pct is not None:
                # StrategyORM stores as percentage (50 = 50%), convert to fraction
                rules['profit_target_pct'] = float(strategy.profit_target_pct) / 100
            if hasattr(strategy, 'stop_loss_pct') and strategy.stop_loss_pct is not None:
                rules['stop_loss_pct'] = float(strategy.stop_loss_pct) / 100
            if hasattr(strategy, 'dte_exit') and strategy.dte_exit is not None:
                rules['exit_dte'] = int(strategy.dte_exit)

        # From trade notes — parse "Exit: TP 50% | SL 2× credit | close ≤21 DTE"
        notes = trade.notes or ''
        if 'Exit:' in notes or 'exit:' in notes:
            parsed = self._parse_exit_notes(notes)
            rules.update(parsed)

        # Detect credit vs debit from trade notes or entry price
        if 'order_side' not in rules:
            entry = Decimal(str(trade.entry_price or 0))
            # Credit trades have positive entry_price, debit negative
            rules['order_side'] = 'credit' if entry > 0 else 'debit'

        # Apply exit profile by strategy type
        strategy_type = (strategy.strategy_type if strategy else '').lower()
        profile = _get_exit_profile(strategy_type, rules.get('order_side', 'credit'))

        if 'profit_target_pct' not in rules:
            rules['profit_target_pct'] = profile['profit_target_pct']
        if 'stop_loss_pct' not in rules:
            rules['stop_loss_pct'] = profile['stop_loss_pct']  # None = no stop (defined risk)
        if 'exit_dte' not in rules:
            rules['exit_dte'] = profile['exit_dte']  # None = hold through expiration

        return rules

    def _parse_exit_notes(self, notes: str) -> Dict:
        """Parse exit rules from trade notes text."""
        rules = {}

        # "TP 50%" or "profit 50%"
        tp_match = re.search(r'TP\s+(\d+)%', notes, re.IGNORECASE)
        if tp_match:
            rules['profit_target_pct'] = int(tp_match.group(1)) / 100

        # "SL 2× credit" or "SL 200%"
        sl_match = re.search(r'SL\s+(\d+(?:\.\d+)?)\s*[×x]', notes, re.IGNORECASE)
        if sl_match:
            rules['stop_loss_pct'] = float(sl_match.group(1))
        else:
            sl_pct_match = re.search(r'SL\s+(\d+)%', notes, re.IGNORECASE)
            if sl_pct_match:
                rules['stop_loss_pct'] = int(sl_pct_match.group(1)) / 100

        # "close ≤21 DTE" or "close by 21 DTE" or "exit 21 DTE"
        dte_match = re.search(r'(?:close|exit)\s*(?:≤|<=|by)?\s*(\d+)\s*DTE', notes, re.IGNORECASE)
        if dte_match:
            rules['exit_dte'] = int(dte_match.group(1))

        # "credit" or "debit" in notes
        if 'credit' in notes.lower():
            rules['order_side'] = 'credit'
        elif 'debit' in notes.lower():
            rules['order_side'] = 'debit'

        return rules
