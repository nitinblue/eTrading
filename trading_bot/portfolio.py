# trading_bot/portfolio.py
from typing import List
from .positions import PositionsManager
from .risk import RiskManager

class Portfolio:
    """Core portfolio class, integrates positions and risk."""
    def __init__(self, positions_manager: PositionsManager, risk_manager: RiskManager):
        self.positions_manager = positions_manager
        self.risk_manager = risk_manager
        self.total_value: float = 0.0

    def update(self):
        self.positions_manager.refresh()
        self.total_value = sum(p.calculate_pnl() for p in self.positions_manager.positions)  # Plus capital
        self.risk_manager.assess(self.positions_manager.positions)

    def get_net_greeks(self) -> Dict:
        net = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
        for p in self.positions_manager.positions:
            for greek in net:
                net[greek] += p.greeks.get(greek, 0) * p.quantity
        return net