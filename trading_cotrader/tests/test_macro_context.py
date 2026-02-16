"""
Tests for macro context short-circuit logic.

Validates that MacroContextService correctly gates screener execution
based on VIX levels and user overrides.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from trading_cotrader.services.macro_context_service import (
    MacroContextService, MacroOverride, MacroAssessment,
)


class TestMacroOverrides:
    """Tests for user-provided macro overrides."""

    def test_risk_off_blocks_screening(self):
        """uncertain + extreme → should_screen=False."""
        macro = MacroContextService()
        override = MacroOverride(
            market_probability='uncertain',
            expected_volatility='extreme',
        )
        assessment = macro.evaluate(override=override)

        assert assessment.should_screen is False
        assert assessment.regime == 'risk_off'
        assert assessment.confidence_modifier == 0.0

    def test_risk_on_allows_screening(self):
        """bullish + low → should_screen=True, modifier=1.0."""
        macro = MacroContextService()
        override = MacroOverride(
            market_probability='bullish',
            expected_volatility='low',
        )
        assessment = macro.evaluate(override=override)

        assert assessment.should_screen is True
        assert assessment.regime == 'risk_on'
        assert assessment.confidence_modifier == 1.0

    def test_cautious_reduces_confidence(self):
        """bearish + high → cautious, modifier=0.6."""
        macro = MacroContextService()
        override = MacroOverride(
            market_probability='bearish',
            expected_volatility='high',
        )
        assessment = macro.evaluate(override=override)

        assert assessment.should_screen is True
        assert assessment.regime == 'cautious'
        assert assessment.confidence_modifier == pytest.approx(0.6)

    def test_neutral_no_modification(self):
        """neutral + normal → neutral, modifier=1.0."""
        macro = MacroContextService()
        override = MacroOverride(
            market_probability='neutral',
            expected_volatility='normal',
        )
        assessment = macro.evaluate(override=override)

        assert assessment.should_screen is True
        assert assessment.regime == 'neutral'
        assert assessment.confidence_modifier == 1.0


class TestAutoAssessment:
    """Tests for VIX-based auto-assessment."""

    def test_no_override_auto_assesses(self):
        """No override, no broker → uses default VIX=18 → neutral."""
        macro = MacroContextService(broker=None)
        # Pass empty override to skip file loading
        assessment = macro.evaluate(override=MacroOverride())

        # Empty override has no market_probability/expected_volatility → falls through to auto
        assert assessment.should_screen is True
        # Default VIX is 18 → neutral
        assert assessment.regime == 'neutral'

    def test_high_vix_cautious(self):
        """VIX=30 → cautious, modifier=0.6."""
        macro = MacroContextService(broker=None)

        with patch.object(macro, '_get_vix', return_value=Decimal('30')):
            assessment = macro._auto_assess()

        assert assessment.regime == 'cautious'
        assert assessment.confidence_modifier == 0.6
        assert assessment.should_screen is True

    def test_extreme_vix_risk_off(self):
        """VIX=40 → risk_off, should_screen=False."""
        macro = MacroContextService(broker=None)

        with patch.object(macro, '_get_vix', return_value=Decimal('40')):
            assessment = macro._auto_assess()

        assert assessment.regime == 'risk_off'
        assert assessment.should_screen is False

    def test_low_vix_risk_on(self):
        """VIX=12 → risk_on, modifier=1.0."""
        macro = MacroContextService(broker=None)

        with patch.object(macro, '_get_vix', return_value=Decimal('12')):
            assessment = macro._auto_assess()

        assert assessment.regime == 'risk_on'
        assert assessment.confidence_modifier == 1.0
        assert assessment.should_screen is True
