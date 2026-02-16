"""
Tests for portfolio management and strategy routing.

Validates:
- Active strategies are a subset of allowed strategies
- Strategy validation allows/blocks correctly
- Portfolio initialization from config
- Capital allocation sums
"""

import pytest
from decimal import Decimal

from trading_cotrader.config.risk_config_loader import (
    PortfolioConfig, PortfoliosConfig, PortfolioRiskLimits,
)
from trading_cotrader.services.portfolio_manager import PortfolioManager


def _build_test_config() -> PortfoliosConfig:
    """Build a PortfoliosConfig for testing (no YAML file needed)."""
    return PortfoliosConfig(portfolios={
        'core_holdings': PortfolioConfig(
            name='core_holdings',
            display_name='Core Holdings',
            description='Long-term holdings',
            capital_allocation_pct=40,
            initial_capital=100000,
            allowed_strategies=['buy_stock', 'covered_call', 'protective_put', 'collar'],
            active_strategies=['buy_stock', 'covered_call'],
            risk_limits=PortfolioRiskLimits(max_portfolio_delta=200, max_positions=20),
        ),
        'medium_risk': PortfolioConfig(
            name='medium_risk',
            display_name='Medium Risk',
            description='Medium-term options',
            capital_allocation_pct=20,
            initial_capital=50000,
            allowed_strategies=['vertical_spread', 'iron_condor', 'calendar_spread'],
            active_strategies=[],  # empty → defaults to allowed
            risk_limits=PortfolioRiskLimits(max_portfolio_delta=300),
        ),
        'high_risk': PortfolioConfig(
            name='high_risk',
            display_name='High Risk',
            description='Short-term trades',
            capital_allocation_pct=10,
            initial_capital=25000,
            allowed_strategies=['iron_condor', 'iron_butterfly', 'straddle', 'strangle'],
            active_strategies=['iron_condor', 'iron_butterfly'],
            risk_limits=PortfolioRiskLimits(max_portfolio_delta=500),
        ),
    })


class TestActiveStrategies:
    """Active strategies configuration."""

    def test_active_strategies_subset(self):
        """active_strategies is a subset of allowed_strategies."""
        config = _build_test_config()
        core = config.get_by_name('core_holdings')
        active = set(core.get_active_strategies())
        allowed = set(core.allowed_strategies)
        assert active.issubset(allowed)

    def test_active_strategies_fallback(self):
        """No active_strategies → defaults to allowed_strategies."""
        config = _build_test_config()
        medium = config.get_by_name('medium_risk')
        assert medium.active_strategies == []
        assert medium.get_active_strategies() == medium.allowed_strategies


class TestStrategyValidation:
    """Strategy validation against portfolio permissions."""

    def test_strategy_validation_allowed(self):
        """iron_condor in high_risk → allowed."""
        config = _build_test_config()
        pm = _create_pm_with_config(config)
        result = pm.validate_trade_for_portfolio('high_risk', 'iron_condor')
        assert result['allowed'] is True

    def test_strategy_validation_blocked(self):
        """iron_condor in core_holdings → blocked."""
        config = _build_test_config()
        pm = _create_pm_with_config(config)
        result = pm.validate_trade_for_portfolio('core_holdings', 'iron_condor')
        assert result['allowed'] is False
        assert 'not allowed' in result['reason'].lower()


class TestPortfolioInitialization:
    """Portfolio creation from config."""

    def test_portfolio_initialization(self, session):
        """4 portfolios (3 test + check count) created from config."""
        config = _build_test_config()
        pm = PortfolioManager(session, config=config)
        portfolios = pm.initialize_portfolios(total_capital=Decimal('250000'))
        assert len(portfolios) == 3

    def test_capital_allocation_sum(self):
        """Total allocation ≤ 100%."""
        config = _build_test_config()
        total = config.total_allocation_pct()
        assert total <= 100.0


# =============================================================================
# Helpers
# =============================================================================

def _create_pm_with_config(config: PortfoliosConfig) -> PortfolioManager:
    """Create a PortfolioManager that doesn't touch the DB for validation-only tests."""

    class FakePM(PortfolioManager):
        """Override __init__ to skip session/repo setup for pure config tests."""
        def __init__(self, portfolios_config):
            self.session = None
            self.repo = None
            self.portfolios_config = portfolios_config

    return FakePM(config)
