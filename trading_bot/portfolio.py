# trading_bot/portfolio.py
from typing import List, Dict
from trading_bot.positions import PositionsManager, Position
from trading_bot.risk import RiskManager
import logging


logger = logging.getLogger(__name__)

class Portfolio:
    def __init__(self, positions_manager: PositionsManager, risk_manager: RiskManager):
        self.positions_manager = positions_manager
        self.risk_manager = risk_manager
        self.total_value: float = 0.0

    def update(self):
        self.positions_manager.refresh()
        # Get capital from broker
        balance = self.positions_manager.broker.get_account_balance()
        capital = balance.get('equity', 100000.0)
        
        self.total_value = sum(p.calculate_pnl() for p in self.positions_manager.positions)
        
        try:
            self.risk_manager.assess(self.positions_manager.positions, capital)
        except ValueError as e:
            logger.error(f"Risk assessment failed: {e}")
            raise

    def get_net_greeks(self) -> Dict:
        net = {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}
        for p in self.positions_manager.positions:
            for greek in net:
                net[greek] += p.greeks.get(greek, 0.0) * p.quantity
        return net