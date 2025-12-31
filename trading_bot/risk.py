# trading_bot/risk.py
from typing import Dict, List
from trading_bot.positions import Position
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, config: Dict):
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.01)
        self.max_portfolio_risk = config.get('max_portfolio_risk', 0.05)  # As fraction (e.g., 0.05 = 5%)

    def assess(self, positions: List[Position], account_capital: float = 100000.0):
        """
        Assess portfolio risk as % of capital.
        account_capital: Total equity (from broker balance)
        """
        total_loss = sum(abs(p.calculate_pnl()) for p in positions if p.calculate_pnl() < 0)
        risk_percentage = total_loss / account_capital if account_capital > 0 else 0

        if risk_percentage > self.max_portfolio_risk:
            logger.warning(f"Portfolio risk {risk_percentage:.2%} > {self.max_portfolio_risk:.2%}")
            raise ValueError("Portfolio risk exceeded")

        logger.info(f"Portfolio risk: {risk_percentage:.2%} (within limit)")