"""
Tests for numerical accuracy of pricing and Greeks.

Validates Black-Scholes pricing, Greeks ranges, put-call parity,
and Decimal precision through round-trips.
"""

import pytest
from decimal import Decimal
import numpy as np

from trading_cotrader.analytics.pricing.option_pricer import OptionPricer, price_option
from trading_cotrader.analytics.greeks.engine import GreeksEngine
import trading_cotrader.core.models.domain as dm


# Common test parameters
SPOT = 450.0
STRIKE = 455.0
TTE = 45 / 365  # ~45 days
VOL = 0.25
RATE = 0.053
DIV = 0.013


class TestBlackScholesPricing:
    """Black-Scholes pricing accuracy."""

    def test_put_call_parity(self):
        """C - P = S*e^(-qT) - K*e^(-rT) must hold."""
        call = OptionPricer.price('call', SPOT, STRIKE, TTE, VOL, RATE, DIV)
        put = OptionPricer.price('put', SPOT, STRIKE, TTE, VOL, RATE, DIV)

        lhs = call - put
        rhs = SPOT * np.exp(-DIV * TTE) - STRIKE * np.exp(-RATE * TTE)

        assert lhs == pytest.approx(rhs, abs=0.01), (
            f"Put-call parity violated: C-P={lhs:.4f}, S*e^(-qT)-K*e^(-rT)={rhs:.4f}"
        )

    def test_atm_call_price_range(self):
        """ATM call price should be in a reasonable range."""
        atm_call = OptionPricer.price('call', SPOT, SPOT, TTE, VOL, RATE, DIV)
        # ATM call ≈ S * sigma * sqrt(T) / sqrt(2*pi) for short-dated
        approx_atm = SPOT * VOL * np.sqrt(TTE) * 0.4  # rough approximation
        assert 0 < atm_call < SPOT
        assert atm_call == pytest.approx(approx_atm, rel=0.5)  # within 50%

    def test_deep_itm_call(self):
        """Deep ITM call ≈ intrinsic value + small time value."""
        deep_itm_call = OptionPricer.price('call', 500, 400, TTE, VOL, RATE, DIV)
        intrinsic = 500 - 400
        assert deep_itm_call >= intrinsic * 0.95  # at least 95% of intrinsic

    def test_deep_otm_call(self):
        """Deep OTM call ≈ 0."""
        deep_otm_call = OptionPricer.price('call', 400, 600, TTE, VOL, RATE, DIV)
        assert deep_otm_call < 1.0  # near zero

    def test_expired_call_intrinsic(self):
        """Expired ITM call = intrinsic value."""
        expired = OptionPricer.price('call', 460, 450, 0, VOL, RATE, DIV)
        assert expired == pytest.approx(10.0, abs=0.01)

    def test_expired_otm_call_zero(self):
        """Expired OTM call = 0."""
        expired = OptionPricer.price('call', 440, 450, 0, VOL, RATE, DIV)
        assert expired == pytest.approx(0.0, abs=0.01)

    def test_price_option_returns_decimal(self):
        """Convenience wrapper returns Decimal."""
        result = price_option('call', SPOT, STRIKE, TTE, VOL, RATE, DIV)
        assert isinstance(result, Decimal)
        assert result > 0


class TestGreeksAccuracy:
    """Greeks engine accuracy."""

    def test_call_delta_range(self):
        """Call delta must be in [0, 1]."""
        engine = GreeksEngine(risk_free_rate=RATE)
        greeks = engine.calculate_greeks('call', SPOT, STRIKE, TTE, VOL, DIV)
        assert 0 <= float(greeks.delta) <= 1

    def test_put_delta_range(self):
        """Put delta must be in [-1, 0]."""
        engine = GreeksEngine(risk_free_rate=RATE)
        greeks = engine.calculate_greeks('put', SPOT, STRIKE, TTE, VOL, DIV)
        assert -1 <= float(greeks.delta) <= 0

    def test_theta_negative_for_long(self):
        """Theta is negative for long options (time decay hurts)."""
        engine = GreeksEngine(risk_free_rate=RATE)
        greeks = engine.calculate_greeks('call', SPOT, STRIKE, TTE, VOL, DIV)
        assert float(greeks.theta) < 0  # theta is per-day, negative for long

    def test_vega_positive(self):
        """Vega is positive (options gain value with higher IV)."""
        engine = GreeksEngine(risk_free_rate=RATE)
        greeks = engine.calculate_greeks('call', SPOT, STRIKE, TTE, VOL, DIV)
        assert float(greeks.vega) > 0

    def test_gamma_positive(self):
        """Gamma is positive for long options."""
        engine = GreeksEngine(risk_free_rate=RATE)
        greeks = engine.calculate_greeks('call', SPOT, STRIKE, TTE, VOL, DIV)
        assert float(greeks.gamma) > 0


class TestPnLCalculations:
    """P&L calculation accuracy."""

    def test_long_call_profit(self):
        """P&L for a profitable long call."""
        leg = dm.Leg(
            symbol=dm.Symbol(
                ticker='SPY', asset_type=dm.AssetType.OPTION,
                option_type=dm.OptionType.CALL, strike=Decimal('450'),
                expiration=dm.datetime(2026, 3, 20),
            ),
            quantity=1,
            side=dm.OrderSide.BUY_TO_OPEN,
            entry_price=Decimal('5.00'),
            current_price=Decimal('8.00'),
        )
        pnl = leg.unrealized_pnl()
        # (8.00 - 5.00) * 1 * 100 = 300
        assert pnl == Decimal('300')

    def test_short_put_profit(self):
        """P&L for a profitable short put (price drops)."""
        leg = dm.Leg(
            symbol=dm.Symbol(
                ticker='SPY', asset_type=dm.AssetType.OPTION,
                option_type=dm.OptionType.PUT, strike=Decimal('450'),
                expiration=dm.datetime(2026, 3, 20),
            ),
            quantity=-1,
            side=dm.OrderSide.SELL_TO_OPEN,
            entry_price=Decimal('3.00'),
            current_price=Decimal('1.50'),
        )
        pnl = leg.unrealized_pnl()
        # (1.50 - 3.00) * -1 * 100 = 150
        assert pnl == Decimal('150')

    def test_decimal_precision_through_greeks(self):
        """Decimal values don't lose precision in Greeks operations."""
        g1 = dm.Greeks(
            delta=Decimal('0.3000'),
            gamma=Decimal('0.0200'),
            theta=Decimal('-0.0500'),
            vega=Decimal('0.1200'),
        )
        g2 = dm.Greeks(
            delta=Decimal('-0.3000'),
            gamma=Decimal('0.0200'),
            theta=Decimal('-0.0500'),
            vega=Decimal('0.1200'),
        )
        summed = g1 + g2
        assert summed.delta == Decimal('0')
        assert summed.gamma == Decimal('0.0400')
        assert summed.theta == Decimal('-0.1000')
        assert summed.vega == Decimal('0.2400')
