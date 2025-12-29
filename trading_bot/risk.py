# trading_bot/risk.py
from typing import List
from .positions import Position

class RiskManager:
    """Core risk management, configurable thresholds."""
    def __init__(self, config: Dict):
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.01)
        self.max_portfolio_risk = config.get('max_portfolio_risk', 0.05)

    def assess(self, positions: List[Position]):
        total_risk = sum(abs(p.calculate_pnl()) for p in positions if p.calculate_pnl() < 0)  # Simplified VaR
        if total_risk > self.max_portfolio_risk:
            raise ValueError("Portfolio risk exceeded")
        # Add more: Diversification, concentration checks