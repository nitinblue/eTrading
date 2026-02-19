"""
Tests for ConditionEvaluator — generic condition evaluation engine.

Tests:
1. All 7 operators (gt, gte, lt, lte, eq, between, in)
2. Reference comparisons (price > sma_20)
3. Multiplier (volume >= 1.5x avg_volume_20)
4. AND logic (evaluate_all) and OR logic (evaluate_any)
5. Global context indicators (vix, days_to_earnings)
6. Categorical `in` operator (directional_regime in ["D","F"])
7. Missing/None indicator values handled gracefully
8. Trade context (pnl_pct, days_held)
"""

import pytest
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

from trading_cotrader.services.research.condition_evaluator import (
    Condition, ConditionEvaluator, parse_conditions,
)


# Mock TechnicalSnapshot for testing
@dataclass
class MockSnapshot:
    current_price: Decimal = Decimal('500')
    bollinger_middle: Decimal = Decimal('495')   # sma_20 proxy
    sma_50: Decimal = Decimal('480')
    sma_200: Decimal = Decimal('460')
    ema_20: Decimal = Decimal('498')
    ema_50: Decimal = Decimal('485')
    rsi_14: float = 45.0
    atr_14: Decimal = Decimal('8.50')
    atr_percent: float = 0.017
    iv_rank: float = 55.0
    iv_percentile: float = 60.0
    pct_from_52w_high: float = -5.0
    directional_regime: str = "F"
    volatility_regime: str = "NORMAL"
    bollinger_upper: Decimal = Decimal('520')
    bollinger_lower: Decimal = Decimal('470')
    bollinger_width: float = 0.05
    vwap: Decimal = Decimal('502')
    high_52w: Decimal = Decimal('526')
    low_52w: Decimal = Decimal('410')
    nearest_support: Decimal = Decimal('460')
    nearest_resistance: Decimal = Decimal('526')
    volume: int = 5000000
    avg_volume_20: int = 4000000


class TestOperators:
    """Test all 7 comparison operators."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot()

    def test_gt_passes(self):
        cond = Condition(indicator='rsi_14', operator='gt', value=40)
        passed, details = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True
        assert details['rsi_14']['passed'] is True

    def test_gt_fails(self):
        cond = Condition(indicator='rsi_14', operator='gt', value=50)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False

    def test_gte_passes_equal(self):
        cond = Condition(indicator='rsi_14', operator='gte', value=45.0)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_gte_passes_greater(self):
        cond = Condition(indicator='rsi_14', operator='gte', value=40)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_lt_passes(self):
        cond = Condition(indicator='rsi_14', operator='lt', value=50)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_lt_fails(self):
        cond = Condition(indicator='rsi_14', operator='lt', value=40)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False

    def test_lte_passes_equal(self):
        cond = Condition(indicator='rsi_14', operator='lte', value=45.0)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_eq_passes(self):
        cond = Condition(indicator='rsi_14', operator='eq', value=45.0)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_eq_fails(self):
        cond = Condition(indicator='rsi_14', operator='eq', value=50.0)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False

    def test_between_passes(self):
        cond = Condition(indicator='rsi_14', operator='between', value=[30, 60])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_between_fails_below(self):
        cond = Condition(indicator='rsi_14', operator='between', value=[50, 70])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False

    def test_between_boundary_inclusive(self):
        cond = Condition(indicator='rsi_14', operator='between', value=[45, 60])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_in_passes_categorical(self):
        cond = Condition(indicator='directional_regime', operator='in', value=["D", "F"])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True

    def test_in_fails_categorical(self):
        cond = Condition(indicator='directional_regime', operator='in', value=["U"])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False

    def test_in_volatility_regime(self):
        cond = Condition(indicator='volatility_regime', operator='in', value=["NORMAL", "HIGH"])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True


class TestReferenceComparisons:
    """Test comparing one indicator against another."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot()  # price=500, sma_20(bollinger_middle)=495

    def test_price_gt_sma_20(self):
        cond = Condition(indicator='price', operator='gt', reference='sma_20')
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True  # 500 > 495

    def test_price_lte_bollinger_lower_fails(self):
        cond = Condition(indicator='price', operator='lte', reference='bollinger_lower')
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False  # 500 > 470

    def test_price_gte_bollinger_upper_fails(self):
        cond = Condition(indicator='price', operator='gte', reference='bollinger_upper')
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False  # 500 < 520


class TestMultiplier:
    """Test multiplier applied to reference values."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot()  # volume=5M, avg_volume_20=4M

    def test_volume_gte_1_5x_avg_passes(self):
        # 5M >= 1.5 * 4M = 6M → False
        cond = Condition(
            indicator='volume', operator='gte',
            reference='avg_volume_20', multiplier=1.5,
        )
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is False  # 5M < 6M

    def test_volume_gte_1_0x_avg_passes(self):
        # 5M >= 1.0 * 4M = 4M → True
        cond = Condition(
            indicator='volume', operator='gte',
            reference='avg_volume_20', multiplier=1.0,
        )
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True


class TestAndOrLogic:
    """Test evaluate_all (AND) and evaluate_any (OR)."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot()

    def test_all_conditions_pass(self):
        conditions = [
            Condition(indicator='rsi_14', operator='lte', value=50),
            Condition(indicator='iv_rank', operator='gte', value=50),
        ]
        passed, details = self.evaluator.evaluate_all(conditions, self.snap)
        assert passed is True
        assert details['rsi_14']['passed'] is True
        assert details['iv_rank']['passed'] is True

    def test_one_condition_fails_and(self):
        conditions = [
            Condition(indicator='rsi_14', operator='lte', value=50),  # passes
            Condition(indicator='iv_rank', operator='gte', value=80),  # fails (55 < 80)
        ]
        passed, details = self.evaluator.evaluate_all(conditions, self.snap)
        assert passed is False
        assert details['rsi_14']['passed'] is True
        assert details['iv_rank']['passed'] is False

    def test_any_one_passes_or(self):
        conditions = [
            Condition(indicator='rsi_14', operator='gte', value=80),  # fails
            Condition(indicator='iv_rank', operator='gte', value=50),  # passes
        ]
        passed, details = self.evaluator.evaluate_any(conditions, self.snap)
        assert passed is True

    def test_none_passes_or(self):
        conditions = [
            Condition(indicator='rsi_14', operator='gte', value=80),  # fails
            Condition(indicator='iv_rank', operator='gte', value=80),  # fails
        ]
        passed, details = self.evaluator.evaluate_any(conditions, self.snap)
        assert passed is False

    def test_empty_conditions_and(self):
        passed, details = self.evaluator.evaluate_all([], self.snap)
        assert passed is True  # vacuously true
        assert details == {}

    def test_empty_conditions_or(self):
        passed, details = self.evaluator.evaluate_any([], self.snap)
        assert passed is False  # nothing to match
        assert details == {}


class TestGlobalContext:
    """Test indicators resolved from global context dict."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot()

    def test_vix_from_context(self):
        cond = Condition(indicator='vix', operator='gte', value=25)
        context = {'vix': 30.5}
        passed, details = self.evaluator.evaluate_all([cond], self.snap, context)
        assert passed is True
        assert details['vix']['actual'] == 30.5

    def test_vix_missing_from_context(self):
        cond = Condition(indicator='vix', operator='gte', value=25)
        passed, details = self.evaluator.evaluate_all([cond], self.snap, {})
        assert passed is False
        assert details['vix']['actual'] is None

    def test_days_to_earnings_between(self):
        cond = Condition(indicator='days_to_earnings', operator='between', value=[2, 7])
        context = {'days_to_earnings': 5}
        passed, _ = self.evaluator.evaluate_all([cond], self.snap, context)
        assert passed is True

    def test_days_to_earnings_outside_range(self):
        cond = Condition(indicator='days_to_earnings', operator='between', value=[2, 7])
        context = {'days_to_earnings': 10}
        passed, _ = self.evaluator.evaluate_all([cond], self.snap, context)
        assert passed is False


class TestTradeContext:
    """Test exit condition indicators from trade context."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot()

    def test_pnl_pct_take_profit(self):
        cond = Condition(indicator='pnl_pct', operator='gte', value=50)
        trade_ctx = {'pnl_pct': 65.0}
        passed, _ = self.evaluator.evaluate_any([cond], self.snap, {}, trade_ctx)
        assert passed is True

    def test_pnl_pct_stop_loss(self):
        cond = Condition(indicator='pnl_pct', operator='lte', value=-100)
        trade_ctx = {'pnl_pct': -120.0}
        passed, _ = self.evaluator.evaluate_any([cond], self.snap, {}, trade_ctx)
        assert passed is True

    def test_days_held_exit(self):
        cond = Condition(indicator='days_held', operator='gte', value=30)
        trade_ctx = {'days_held': 35}
        passed, _ = self.evaluator.evaluate_any([cond], self.snap, {}, trade_ctx)
        assert passed is True

    def test_trade_context_missing(self):
        cond = Condition(indicator='pnl_pct', operator='gte', value=50)
        passed, details = self.evaluator.evaluate_any([cond], self.snap, {}, {})
        assert passed is False


class TestMissingIndicators:
    """Test graceful handling of missing/None indicators."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()

    def test_none_snapshot(self):
        cond = Condition(indicator='rsi_14', operator='gte', value=50)
        passed, details = self.evaluator.evaluate_all([cond], None)
        assert passed is False
        assert details['rsi_14']['actual'] is None

    def test_missing_field_on_snapshot(self):
        @dataclass
        class PartialSnapshot:
            rsi_14: Optional[float] = None
        snap = PartialSnapshot()
        cond = Condition(indicator='rsi_14', operator='gte', value=50)
        passed, details = self.evaluator.evaluate_all([cond], snap)
        assert passed is False

    def test_missing_reference(self):
        @dataclass
        class MinimalSnapshot:
            current_price: Decimal = Decimal('100')
        snap = MinimalSnapshot()
        cond = Condition(indicator='price', operator='gt', reference='sma_200')
        passed, details = self.evaluator.evaluate_all([cond], snap)
        assert passed is False
        assert 'not available' in details['price'].get('reason', '')


class TestParseConditions:
    """Test parsing conditions from YAML-like dicts."""

    def test_parse_simple(self):
        raw = [
            {'indicator': 'rsi_14', 'operator': 'lte', 'value': 40},
            {'indicator': 'vix', 'operator': 'between', 'value': [22, 45]},
        ]
        conditions = parse_conditions(raw)
        assert len(conditions) == 2
        assert conditions[0].indicator == 'rsi_14'
        assert conditions[0].operator == 'lte'
        assert conditions[0].value == 40
        assert conditions[1].value == [22, 45]

    def test_parse_with_reference(self):
        raw = [
            {'indicator': 'price', 'operator': 'gt', 'reference': 'sma_20'},
        ]
        conditions = parse_conditions(raw)
        assert conditions[0].reference == 'sma_20'
        assert conditions[0].value is None

    def test_parse_with_multiplier(self):
        raw = [
            {'indicator': 'volume', 'operator': 'gte', 'reference': 'avg_volume_20', 'multiplier': 1.5},
        ]
        conditions = parse_conditions(raw)
        assert conditions[0].multiplier == 1.5

    def test_parse_empty(self):
        assert parse_conditions([]) == []


class TestNegativeDecimalComparisons:
    """Test pct_from_52w_high (negative values) with between."""

    def setup_method(self):
        self.evaluator = ConditionEvaluator()
        self.snap = MockSnapshot(pct_from_52w_high=-10.0)

    def test_between_negative_range(self):
        cond = Condition(indicator='pct_from_52w_high', operator='between', value=[-15.0, -8.0])
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True  # -10 is between -15 and -8

    def test_between_negative_range_outside(self):
        snap = MockSnapshot(pct_from_52w_high=-3.0)
        cond = Condition(indicator='pct_from_52w_high', operator='between', value=[-15.0, -8.0])
        passed, _ = self.evaluator.evaluate_all([cond], snap)
        assert passed is False  # -3 > -8

    def test_lte_negative(self):
        cond = Condition(indicator='pct_from_52w_high', operator='lte', value=-8.0)
        passed, _ = self.evaluator.evaluate_all([cond], self.snap)
        assert passed is True  # -10 <= -8
