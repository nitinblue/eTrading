# tests/unit/test_risk.py
import pytest
from trading_bot.risk import RiskManager
from trading_bot.positions import Position

def test_risk_manager_portfolio_limit_exceeded(risk_config):
    risk_mgr = RiskManager(risk_config)

    # Simulate losing positions exceeding limit
    positions = [
        Position('AAPL', 1, 100.0, 90.0, {}),  # Loss of 10 per share, but adjust for risk calc
        Position('TSLA', 1, 200.0, 150.0, {})   # Assume risk calc in assess() is sum of negative PnL
    ]

    with pytest.raises(ValueError, match="Portfolio risk exceeded"):
        risk_mgr.assess(positions)

def test_risk_manager_within_limits(risk_config):
    risk_mgr = RiskManager(risk_config)

    positions = [
        Position('AAPL', 1, 100.0, 99.0, {})  # Small loss
    ]

    risk_mgr.assess(positions)  # No raise