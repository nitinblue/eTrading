# trading_bot/portfolio.py
from typing import Dict, List
from .positions import PositionsManager, Position
from .risk import RiskManager
import logging

logger = logging.getLogger(__name__)

class Portfolio:
    def __init__(self, positions_manager: PositionsManager, risk_manager: RiskManager):
        self.positions_manager = positions_manager
        self.risk_manager = risk_manager
        self.broker = positions_manager.broker  # ← Add this line to access broker
        self.total_value: float = 0.0

    async def update(self):
        await self.positions_manager.refresh()
        balance = self.broker.get_account_balance()  # Now works
        capital = balance.get('equity', 100000.0)
        
        self.total_value = sum(p.calculate_pnl() for p in self.positions_manager.positions)
        
        try:
            self.risk_manager.assess(self.positions_manager.positions, capital)
        except ValueError as e:
            logger.error(f"Risk assessment failed: {e}")
            raise

    def get_net_greeks(self) -> Dict:       
        net = {g: 0.0 for g in ['delta', 'gamma', 'theta', 'vega', 'rho']}        
        for p in self.positions_manager.positions:
            qty = float(p.quantity)
            for greek in net:
                net[greek] += p.greeks.get(greek, 0.0) * qty
        return net