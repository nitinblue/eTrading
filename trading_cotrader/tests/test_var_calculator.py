"""
Tests for VaR Calculator and Correlation Analyzer.

Tests the core risk calculation pipeline:
- Delta exposure extraction from positions
- Parametric VaR (delta-normal)
- Historical VaR
- Incremental VaR
- Correlation matrix building
- Expected Shortfall (CVaR)

Uses mock position objects to avoid yfinance dependency in unit tests.
"""

import pytest
import numpy as np
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List

from trading_cotrader.services.risk.var_calculator import (
    VaRCalculator, VaRResult, VaRMethod, VaRContribution, _extract_exposures
)
from trading_cotrader.services.risk.correlation import (
    CorrelationAnalyzer, CorrelationMatrix, _fetch_returns
)


# =============================================================================
# Mock position objects for testing (avoid importing full domain model)
# =============================================================================

@dataclass
class MockGreeks:
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')


@dataclass
class MockSymbol:
    ticker: str = 'SPY'
    asset_type: str = 'option'
    is_option: bool = True
    multiplier: int = 100
    option_type: str = 'put'
    strike: Decimal = Decimal('580')
    expiration: Optional[datetime] = None


@dataclass
class MockPosition:
    symbol: MockSymbol = field(default_factory=MockSymbol)
    quantity: int = -1
    current_greeks: Optional[MockGreeks] = None
    current_underlying_price: Decimal = Decimal('0')
    entry_underlying_price: Decimal = Decimal('0')
    current_price: Decimal = Decimal('0')
    entry_price: Decimal = Decimal('0')
    market_value: Decimal = Decimal('0')
    greeks: list = field(default_factory=list)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def spy_short_put():
    """Short 1 SPY put, delta -0.30, SPY at 600."""
    return MockPosition(
        symbol=MockSymbol(ticker='SPY', is_option=True, multiplier=100),
        quantity=-1,
        current_greeks=MockGreeks(delta=Decimal('-0.30')),
        current_underlying_price=Decimal('600'),
        market_value=Decimal('-500'),
    )


@pytest.fixture
def spy_long_call():
    """Long 1 SPY call, delta +0.50, SPY at 600."""
    return MockPosition(
        symbol=MockSymbol(ticker='SPY', is_option=True, multiplier=100, option_type='call'),
        quantity=1,
        current_greeks=MockGreeks(delta=Decimal('0.50')),
        current_underlying_price=Decimal('600'),
        market_value=Decimal('800'),
    )


@pytest.fixture
def qqq_short_put():
    """Short 1 QQQ put, delta -0.25, QQQ at 520."""
    return MockPosition(
        symbol=MockSymbol(ticker='QQQ', is_option=True, multiplier=100),
        quantity=-1,
        current_greeks=MockGreeks(delta=Decimal('-0.25')),
        current_underlying_price=Decimal('520'),
        market_value=Decimal('-400'),
    )


@pytest.fixture
def nvda_equity():
    """Long 100 shares NVDA at 191."""
    return MockPosition(
        symbol=MockSymbol(ticker='NVDA', is_option=False, multiplier=1),
        quantity=100,
        current_price=Decimal('191'),
        entry_price=Decimal('185'),
        market_value=Decimal('19100'),
    )


@pytest.fixture
def calculator():
    """VaR calculator instance."""
    return VaRCalculator()


@pytest.fixture
def correlation_analyzer():
    """Correlation analyzer instance."""
    return CorrelationAnalyzer()


# =============================================================================
# Delta exposure extraction tests
# =============================================================================

class TestDeltaExposure:
    """Test _extract_exposures correctly converts positions to delta-dollar exposures."""

    def test_short_put_exposure(self, spy_short_put):
        """Short 1 SPY put, delta -0.30: exposure = -0.30 * (-1) * 100 * 600 = +18,000."""
        exposures = _extract_exposures([spy_short_put])
        assert 'SPY' in exposures
        assert abs(exposures['SPY'] - 18000.0) < 1.0  # -0.30 * -1 * 100 * 600

    def test_long_call_exposure(self, spy_long_call):
        """Long 1 SPY call, delta +0.50: exposure = 0.50 * 1 * 100 * 600 = +30,000."""
        exposures = _extract_exposures([spy_long_call])
        assert 'SPY' in exposures
        assert abs(exposures['SPY'] - 30000.0) < 1.0

    def test_equity_exposure(self, nvda_equity):
        """Long 100 shares NVDA at 191: exposure = 100 * 191 = 19,100."""
        exposures = _extract_exposures([nvda_equity])
        assert 'NVDA' in exposures
        assert abs(exposures['NVDA'] - 19100.0) < 1.0

    def test_combined_same_underlying(self, spy_short_put, spy_long_call):
        """Multiple SPY positions: exposures aggregate per underlying."""
        exposures = _extract_exposures([spy_short_put, spy_long_call])
        assert 'SPY' in exposures
        # Short put: +18,000 + Long call: +30,000 = +48,000
        assert abs(exposures['SPY'] - 48000.0) < 1.0

    def test_multiple_underlyings(self, spy_short_put, qqq_short_put, nvda_equity):
        """Positions across multiple underlyings create separate exposure entries."""
        exposures = _extract_exposures([spy_short_put, qqq_short_put, nvda_equity])
        assert len(exposures) == 3
        assert 'SPY' in exposures
        assert 'QQQ' in exposures
        assert 'NVDA' in exposures

    def test_empty_positions(self):
        """No positions returns empty dict."""
        exposures = _extract_exposures([])
        assert exposures == {}

    def test_zero_quantity_ignored(self):
        """Positions with zero quantity are skipped."""
        pos = MockPosition(quantity=0)
        exposures = _extract_exposures([pos])
        assert exposures == {}

    def test_no_greeks_option_skipped(self):
        """Option position with no Greeks is skipped."""
        pos = MockPosition(
            symbol=MockSymbol(ticker='SPY', is_option=True),
            quantity=-1,
            current_greeks=None,
        )
        exposures = _extract_exposures([pos])
        assert exposures == {}


# =============================================================================
# Parametric VaR tests
# =============================================================================

class TestParametricVaR:
    """Test parametric (delta-normal) VaR calculation."""

    def test_single_position_var_is_positive(self, calculator, spy_short_put):
        """VaR for any position must be positive (it's a loss amount)."""
        result = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000'), confidence=0.95, horizon_days=1
        )
        assert result.var_amount > 0
        assert result.var_percent > 0
        assert result.method == VaRMethod.PARAMETRIC

    def test_var_scales_with_confidence(self, calculator, spy_short_put):
        """99% VaR must be larger than 95% VaR."""
        var_95 = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000'), confidence=0.95
        )
        var_99 = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000'), confidence=0.99
        )
        assert var_99.var_amount > var_95.var_amount

    def test_var_scales_with_horizon(self, calculator, spy_short_put):
        """5-day VaR must be larger than 1-day VaR (sqrt(5) scaling)."""
        var_1d = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000'), horizon_days=1
        )
        var_5d = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000'), horizon_days=5
        )
        assert var_5d.var_amount > var_1d.var_amount

    def test_diversified_var_less_than_sum(self, calculator, spy_short_put, nvda_equity):
        """Portfolio VaR should be less than sum of individual VaRs (diversification benefit)."""
        var_spy = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000')
        )
        var_nvda = calculator.calculate_parametric_var(
            [nvda_equity], Decimal('100000')
        )
        var_combined = calculator.calculate_parametric_var(
            [spy_short_put, nvda_equity], Decimal('100000')
        )
        # Portfolio VaR should be <= sum of individual VaRs (correlation < 1)
        sum_var = var_spy.var_amount + var_nvda.var_amount
        assert var_combined.var_amount <= sum_var + Decimal('1')  # Small tolerance

    def test_empty_positions_returns_zero(self, calculator):
        """No positions means zero VaR."""
        result = calculator.calculate_parametric_var([], Decimal('100000'))
        assert result.var_amount == Decimal('0')
        assert result.var_percent == Decimal('0')

    def test_result_has_contributions(self, calculator, spy_short_put, qqq_short_put):
        """VaR result should contain per-underlying contributions."""
        result = calculator.calculate_parametric_var(
            [spy_short_put, qqq_short_put], Decimal('100000')
        )
        assert len(result.contributions) == 2
        symbols = {c.symbol for c in result.contributions}
        assert 'SPY' in symbols
        assert 'QQQ' in symbols

    def test_expected_shortfall_greater_than_var(self, calculator, spy_short_put):
        """CVaR (Expected Shortfall) must be >= VaR."""
        result = calculator.calculate_parametric_var(
            [spy_short_put], Decimal('100000'), confidence=0.95
        )
        assert result.expected_shortfall >= result.var_amount

    def test_var_percent_is_consistent(self, calculator, spy_short_put):
        """VaR percent = VaR amount / portfolio value * 100."""
        pv = Decimal('100000')
        result = calculator.calculate_parametric_var([spy_short_put], pv)
        expected_pct = result.var_amount / pv * 100
        assert abs(result.var_percent - expected_pct) < Decimal('0.01')


# =============================================================================
# Incremental VaR tests
# =============================================================================

class TestIncrementalVaR:
    """Test incremental VaR for pre-trade risk assessment."""

    def test_adding_same_direction_increases_var(self, calculator, spy_short_put):
        """Adding a correlated position in same direction should increase VaR."""
        # Another SPY short put
        new_put = MockPosition(
            symbol=MockSymbol(ticker='SPY', is_option=True),
            quantity=-1,
            current_greeks=MockGreeks(delta=Decimal('-0.30')),
            current_underlying_price=Decimal('600'),
            market_value=Decimal('-500'),
        )
        var_before, var_after, incremental = calculator.calculate_incremental_var(
            [spy_short_put], new_put, Decimal('100000')
        )
        assert incremental > Decimal('0')
        assert var_after.var_amount > var_before.var_amount

    def test_adding_hedge_may_reduce_var(self, calculator, spy_short_put):
        """Adding an offsetting position (hedge) should reduce or not increase VaR much."""
        # Long SPY put to offset the short put
        hedge = MockPosition(
            symbol=MockSymbol(ticker='SPY', is_option=True, option_type='put'),
            quantity=1,
            current_greeks=MockGreeks(delta=Decimal('-0.30')),
            current_underlying_price=Decimal('600'),
            market_value=Decimal('500'),
        )
        var_before, var_after, incremental = calculator.calculate_incremental_var(
            [spy_short_put], hedge, Decimal('100000')
        )
        # Hedge should reduce VaR (net delta goes to ~0)
        assert var_after.var_amount < var_before.var_amount

    def test_incremental_returns_three_values(self, calculator, spy_short_put, qqq_short_put):
        """Incremental VaR returns (before, after, change)."""
        var_before, var_after, incremental = calculator.calculate_incremental_var(
            [spy_short_put], qqq_short_put, Decimal('100000')
        )
        assert isinstance(var_before, VaRResult)
        assert isinstance(var_after, VaRResult)
        assert incremental == var_after.var_amount - var_before.var_amount


# =============================================================================
# Correlation matrix tests
# =============================================================================

class TestCorrelationMatrix:
    """Test correlation matrix building and querying."""

    def test_self_correlation_is_one(self, correlation_analyzer):
        """Correlation of any symbol with itself must be 1.0."""
        matrix = correlation_analyzer.calculate_correlation_matrix(['SPY'])
        assert matrix.get_correlation('SPY', 'SPY') == 1.0

    def test_fallback_estimates_work(self):
        """Without yfinance data, fallback estimates should produce a valid matrix."""
        analyzer = CorrelationAnalyzer()
        # Force fallback by using made-up symbols
        matrix = analyzer._build_matrix_from_estimates(['AAA', 'BBB', 'CCC'], 60)
        assert len(matrix.matrix) == 3  # 3 pairs
        for (s1, s2), corr in matrix.matrix.items():
            assert -1 <= corr <= 1

    def test_covariance_matrix_from_returns(self):
        """Building matrix from synthetic returns produces valid covariance."""
        analyzer = CorrelationAnalyzer()
        np.random.seed(42)
        returns = {
            'A': np.random.normal(0, 0.01, 252),
            'B': np.random.normal(0, 0.02, 252),
        }
        matrix = analyzer._build_matrix_from_returns(['A', 'B'], returns, 252)
        assert matrix.covariance_matrix is not None
        assert matrix.covariance_matrix.shape == (2, 2)
        # Diagonal must be positive (variance)
        assert matrix.covariance_matrix[0, 0] > 0
        assert matrix.covariance_matrix[1, 1] > 0
        # Volatilities should be computed
        assert matrix.get_volatility('A') is not None
        assert matrix.get_volatility('B') is not None
        # B should have ~2x volatility of A
        assert matrix.get_volatility('B') > matrix.get_volatility('A')

    def test_correlation_symmetry(self):
        """corr(A,B) == corr(B,A)."""
        analyzer = CorrelationAnalyzer()
        matrix = analyzer._build_matrix_from_estimates(['SPY', 'QQQ'], 60)
        assert matrix.get_correlation('SPY', 'QQQ') == matrix.get_correlation('QQQ', 'SPY')

    def test_volatilities_annualized(self):
        """Volatilities from real data should be annualized (typically 10-80% for equities)."""
        analyzer = CorrelationAnalyzer()
        np.random.seed(42)
        # Daily returns ~1% std = ~16% annualized
        returns = {'X': np.random.normal(0, 0.01, 252)}
        matrix = analyzer._build_matrix_from_returns(['X'], returns, 252)
        vol = matrix.get_volatility('X')
        assert vol is not None
        assert 0.05 < vol < 0.50  # Reasonable range for annualized vol
