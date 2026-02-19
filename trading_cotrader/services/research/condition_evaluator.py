"""
Condition Evaluator — Evaluates entry/exit conditions against market data.

Resolves indicators from 3 sources (checked in order):
  1. TechnicalSnapshot — price, sma_20, rsi_14, bollinger_*, iv_rank, regimes, etc.
  2. Global context — vix, days_to_earnings (populated by agent before evaluation)
  3. Trade context — pnl_pct, days_held (from open trade, exit conditions only)

Operators: gt, gte, lt, lte, eq, between, in
Reference comparisons: price > sma_20 (compare indicator to another indicator)
Multiplier: volume >= 1.5x avg_volume_20
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# Map indicator names to TechnicalSnapshot field names
# Keys that don't map 1:1 to snapshot fields are resolved from context or trade_ctx
_SNAPSHOT_FIELDS = {
    'price': 'current_price',
    'current_price': 'current_price',
    'sma_20': 'bollinger_middle',  # SMA(20) = Bollinger middle
    'sma_50': 'sma_50',
    'sma_200': 'sma_200',
    'ema_20': 'ema_20',
    'ema_50': 'ema_50',
    'rsi_14': 'rsi_14',
    'atr_percent': 'atr_percent',
    'atr_14': 'atr_14',
    'iv_rank': 'iv_rank',
    'iv_percentile': 'iv_percentile',
    'pct_from_52w_high': 'pct_from_52w_high',
    'directional_regime': 'directional_regime',
    'volatility_regime': 'volatility_regime',
    'bollinger_upper': 'bollinger_upper',
    'bollinger_middle': 'bollinger_middle',
    'bollinger_lower': 'bollinger_lower',
    'bollinger_width': 'bollinger_width',
    'vwap': 'vwap',
    'high_52w': 'high_52w',
    'low_52w': 'low_52w',
    'nearest_support': 'nearest_support',
    'nearest_resistance': 'nearest_resistance',
    'volume': 'volume',
    'avg_volume_20': 'avg_volume_20',
}

# Context-level indicators (not on TechnicalSnapshot)
_CONTEXT_FIELDS = {'vix', 'days_to_earnings'}

# Trade-level indicators (only available for exit conditions)
_TRADE_FIELDS = {'pnl_pct', 'days_held'}


@dataclass
class Condition:
    """A single entry or exit condition."""
    indicator: str = ""
    operator: str = ""            # gt, gte, lt, lte, eq, between, in
    value: Any = None             # Scalar or list (for between/in)
    reference: Optional[str] = None   # Compare against another indicator
    multiplier: Optional[float] = None  # Scale reference value

    def __repr__(self) -> str:
        if self.reference:
            mult = f" * {self.multiplier}" if self.multiplier else ""
            return f"Condition({self.indicator} {self.operator} {self.reference}{mult})"
        return f"Condition({self.indicator} {self.operator} {self.value})"


def parse_conditions(raw_list: List[Dict]) -> List[Condition]:
    """Parse raw YAML condition dicts into Condition objects."""
    conditions = []
    for raw in raw_list:
        conditions.append(Condition(
            indicator=raw.get('indicator', ''),
            operator=raw.get('operator', ''),
            value=raw.get('value'),
            reference=raw.get('reference'),
            multiplier=raw.get('multiplier'),
        ))
    return conditions


class ConditionEvaluator:
    """
    Evaluates conditions against TechnicalSnapshot + context.

    evaluate_all() — AND logic: ALL conditions must be true (entry)
    evaluate_any() — OR logic: ANY condition triggers (exit)
    """

    def evaluate_all(
        self,
        conditions: List[Condition],
        snapshot: Any,
        context: Optional[Dict] = None,
        trade_ctx: Optional[Dict] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate ALL conditions (AND logic). Returns (all_passed, details).

        details maps condition indicator to {passed, actual, target, operator}.
        """
        context = context or {}
        trade_ctx = trade_ctx or {}
        details = {}
        all_passed = True

        for cond in conditions:
            passed, detail = self._evaluate_one(cond, snapshot, context, trade_ctx)
            details[cond.indicator] = detail
            if not passed:
                all_passed = False

        return all_passed, details

    def evaluate_any(
        self,
        conditions: List[Condition],
        snapshot: Any,
        context: Optional[Dict] = None,
        trade_ctx: Optional[Dict] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate conditions (OR logic). Returns (any_passed, details).
        """
        context = context or {}
        trade_ctx = trade_ctx or {}
        details = {}
        any_passed = False

        for cond in conditions:
            passed, detail = self._evaluate_one(cond, snapshot, context, trade_ctx)
            details[cond.indicator] = detail
            if passed:
                any_passed = True

        return any_passed, details

    def _evaluate_one(
        self,
        cond: Condition,
        snapshot: Any,
        context: Dict,
        trade_ctx: Dict,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate a single condition. Returns (passed, detail_dict)."""
        actual = self._get_value(cond.indicator, snapshot, context, trade_ctx)

        if actual is None:
            return False, {
                'passed': False, 'actual': None,
                'reason': f'indicator {cond.indicator} not available',
            }

        # Reference comparison: compare indicator vs another indicator
        if cond.reference:
            ref_val = self._get_value(cond.reference, snapshot, context, trade_ctx)
            if ref_val is None:
                return False, {
                    'passed': False, 'actual': actual,
                    'reason': f'reference {cond.reference} not available',
                }
            target = float(ref_val) if not isinstance(ref_val, str) else ref_val
            if cond.multiplier and isinstance(target, (int, float)):
                target = target * cond.multiplier
        else:
            target = cond.value

        passed = self._compare(actual, cond.operator, target)

        return passed, {
            'passed': passed,
            'actual': actual,
            'target': target,
            'operator': cond.operator,
        }

    def _get_value(
        self,
        indicator: str,
        snapshot: Any,
        context: Dict,
        trade_ctx: Dict,
    ) -> Optional[Union[float, str, int]]:
        """
        Resolve an indicator value from snapshot, context, or trade context.

        Returns None if the indicator is unavailable.
        """
        # 1. Try TechnicalSnapshot
        field_name = _SNAPSHOT_FIELDS.get(indicator)
        if field_name and snapshot is not None:
            val = getattr(snapshot, field_name, None)
            if val is not None:
                # Convert Decimal to float for comparison
                if isinstance(val, Decimal):
                    return float(val)
                return val

        # 2. Try global context
        if indicator in _CONTEXT_FIELDS or indicator in context:
            val = context.get(indicator)
            if val is not None:
                if isinstance(val, Decimal):
                    return float(val)
                return val

        # 3. Try trade context
        if indicator in _TRADE_FIELDS or indicator in trade_ctx:
            val = trade_ctx.get(indicator)
            if val is not None:
                if isinstance(val, Decimal):
                    return float(val)
                return val

        return None

    @staticmethod
    def _compare(actual: Any, operator: str, target: Any) -> bool:
        """
        Compare actual value against target using the given operator.

        Handles numeric and categorical comparisons.
        """
        try:
            if operator == 'gt':
                return float(actual) > float(target)
            elif operator == 'gte':
                return float(actual) >= float(target)
            elif operator == 'lt':
                return float(actual) < float(target)
            elif operator == 'lte':
                return float(actual) <= float(target)
            elif operator == 'eq':
                # Support both numeric and string equality
                try:
                    return float(actual) == float(target)
                except (TypeError, ValueError):
                    return str(actual) == str(target)
            elif operator == 'between':
                if not isinstance(target, (list, tuple)) or len(target) != 2:
                    logger.warning(f"between requires [lo, hi], got {target}")
                    return False
                val = float(actual)
                return float(target[0]) <= val <= float(target[1])
            elif operator == 'in':
                if not isinstance(target, (list, tuple)):
                    logger.warning(f"in requires a list, got {target}")
                    return False
                return str(actual) in [str(t) for t in target]
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except (TypeError, ValueError) as e:
            logger.debug(f"Comparison failed: {actual} {operator} {target}: {e}")
            return False
