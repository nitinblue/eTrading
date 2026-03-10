"""
Tests for macro context short-circuit logic.

Validates that MacroContextService correctly gates screener execution
based on MarketAnalyzer context and user overrides.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
import sys

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


class TestMarketAnalyzerAssessment:
    """Tests for MarketAnalyzer-based auto-assessment."""

    def _mock_context(self, env_label, trading_allowed, size_factor, summary="test"):
        """Build a mock MarketContext."""
        ctx = MagicMock()
        ctx.environment_label = env_label
        ctx.trading_allowed = trading_allowed
        ctx.position_size_factor = size_factor
        ctx.summary = summary
        ctx.black_swan = MagicMock()
        ctx.black_swan.indicators = []
        return ctx

    def _run_with_mock_ma(self, ctx):
        """Run evaluate with a mocked MarketAnalyzer context."""
        mock_ma = MagicMock()
        mock_ma_cls = MagicMock(return_value=mock_ma)
        mock_ma.context.assess.return_value = ctx

        mock_module = MagicMock()
        mock_module.MarketAnalyzer = mock_ma_cls

        with patch.dict(sys.modules, {'market_analyzer': mock_module}):
            macro = MacroContextService()
            return macro.evaluate(override=MacroOverride())

    def test_risk_on_from_ma(self):
        """risk-on environment → risk_on regime."""
        ctx = self._mock_context('risk-on', True, 1.0, 'Low vol')
        assessment = self._run_with_mock_ma(ctx)

        assert assessment.regime == 'risk_on'
        assert assessment.should_screen is True
        assert assessment.confidence_modifier == 1.0

    def test_crisis_blocks_screening(self):
        """crisis environment → risk_off, should_screen=False."""
        ctx = self._mock_context('crisis', False, 0.0, 'Black swan CRITICAL')
        assessment = self._run_with_mock_ma(ctx)

        assert assessment.regime == 'risk_off'
        assert assessment.should_screen is False
        assert assessment.confidence_modifier == 0.0

    def test_cautious_reduces_confidence(self):
        """cautious environment → cautious regime, reduced modifier."""
        ctx = self._mock_context('cautious', True, 0.7, 'Elevated vol')
        assessment = self._run_with_mock_ma(ctx)

        assert assessment.regime == 'cautious'
        assert assessment.should_screen is True
        assert assessment.confidence_modifier == 0.7

    def test_defensive_maps_to_cautious(self):
        """defensive environment → cautious regime."""
        ctx = self._mock_context('defensive', True, 0.5, 'Rising rates')
        assessment = self._run_with_mock_ma(ctx)

        assert assessment.regime == 'cautious'
        assert assessment.should_screen is True
        assert assessment.confidence_modifier == 0.5

    def test_ma_failure_falls_back_neutral(self):
        """MarketAnalyzer unavailable → neutral fallback."""
        mock_module = MagicMock()
        mock_module.MarketAnalyzer.side_effect = Exception("MA not installed")

        with patch.dict(sys.modules, {'market_analyzer': mock_module}):
            macro = MacroContextService()
            assessment = macro.evaluate(override=MacroOverride())

        assert assessment.regime == 'neutral'
        assert assessment.should_screen is True
        assert assessment.confidence_modifier == 1.0
        assert 'unavailable' in assessment.rationale.lower()
