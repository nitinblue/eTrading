"""
Tests for screener entry filter logic.

Validates that _check_entry_filters in screener_base.py correctly
evaluates RSI, regime, ATR, and IV percentile conditions.
"""

import pytest
from dataclasses import dataclass
from typing import Optional, List

from trading_cotrader.config.risk_config_loader import (
    RiskConfig, StrategyRule, EntryFilters,
)


# =============================================================================
# Minimal mock for TechnicalSnapshot (avoid importing yfinance dependency)
# =============================================================================

@dataclass
class MockTechnicalSnapshot:
    """Mimics the subset of TechnicalSnapshot used by _check_entry_filters."""
    rsi_14: Optional[float] = None
    directional_regime: Optional[str] = None
    volatility_regime: Optional[str] = None
    atr_percent: Optional[float] = None
    iv_percentile: Optional[float] = None
    iv_rank: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    sma_200: Optional[float] = None


def _make_config_with_filters(strategy_name: str, filters: EntryFilters) -> RiskConfig:
    """Build a RiskConfig with one strategy rule containing the given filters."""
    config = RiskConfig()
    config.strategy_rules[strategy_name] = StrategyRule(
        name=strategy_name,
        entry_filters=filters,
    )
    return config


def _check(strategy_type, tech_snap, risk_config):
    """Call the screener base _check_entry_filters method."""
    from trading_cotrader.services.screeners.screener_base import ScreenerBase

    # Create a concrete subclass so we can call the method
    class TestScreener(ScreenerBase):
        name = "test"
        source = "manual"
        def screen(self, symbols):
            return []

    screener = TestScreener()
    return screener._check_entry_filters(strategy_type, tech_snap, risk_config)


class TestRSIFilters:
    """RSI range checks."""

    def test_rsi_in_range_passes(self):
        snap = MockTechnicalSnapshot(rsi_14=50.0)
        config = _make_config_with_filters('iron_condor', EntryFilters(rsi_range=[30.0, 70.0]))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is True

    def test_rsi_out_of_range_fails(self):
        snap = MockTechnicalSnapshot(rsi_14=75.0)
        config = _make_config_with_filters('iron_condor', EntryFilters(rsi_range=[30.0, 70.0]))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is False
        assert 'RSI' in reason


class TestDirectionalRegimeFilters:
    """Directional regime matching."""

    def test_regime_match(self):
        snap = MockTechnicalSnapshot(directional_regime='F')
        config = _make_config_with_filters('iron_condor', EntryFilters(directional_regime=['F', 'U']))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is True

    def test_regime_mismatch(self):
        snap = MockTechnicalSnapshot(directional_regime='U')
        config = _make_config_with_filters('iron_condor', EntryFilters(directional_regime=['F']))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is False
        assert 'regime' in reason.lower()


class TestATRFilters:
    """ATR percent checks."""

    def test_atr_above_minimum(self):
        snap = MockTechnicalSnapshot(atr_percent=0.012)
        config = _make_config_with_filters('iron_condor', EntryFilters(min_atr_percent=0.008))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is True

    def test_atr_below_minimum(self):
        snap = MockTechnicalSnapshot(atr_percent=0.005)
        config = _make_config_with_filters('iron_condor', EntryFilters(min_atr_percent=0.008))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is False
        assert 'ATR' in reason


class TestEdgeCases:
    """Edge cases and combined filters."""

    def test_no_filters_always_passes(self):
        snap = MockTechnicalSnapshot(rsi_14=90.0, atr_percent=0.001)
        config = RiskConfig()
        # No strategy rule → no filters → pass
        passed, reason = _check('iron_condor', snap, config)
        assert passed is True

    def test_multiple_filters_all_must_pass(self):
        """If one filter passes and another fails → overall fail."""
        snap = MockTechnicalSnapshot(rsi_14=50.0, atr_percent=0.003)
        config = _make_config_with_filters('iron_condor', EntryFilters(
            rsi_range=[30.0, 70.0],  # RSI 50 passes
            min_atr_percent=0.008,    # ATR 0.003 fails
        ))
        passed, reason = _check('iron_condor', snap, config)
        assert passed is False
        assert 'ATR' in reason

    def test_no_technical_data_skips(self):
        """None tech_snap → skip filters (pass)."""
        config = _make_config_with_filters('iron_condor', EntryFilters(rsi_range=[30.0, 70.0]))
        passed, reason = _check('iron_condor', None, config)
        assert passed is True
