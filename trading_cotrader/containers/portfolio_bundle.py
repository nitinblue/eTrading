"""
Portfolio Bundle — Container bundle for one real portfolio + its WhatIf mirror.

Real + WhatIf share positions, trades, and risk factors.
Each bundle is currency-isolated (no USD/INR mixing).

Usage:
    bundle = PortfolioBundle(config_name="tastytrade", currency="USD", ...)
    state = bundle.get_full_state()
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .portfolio_container import PortfolioContainer
from .position_container import PositionContainer
from .risk_factor_container import RiskFactorContainer
from .trade_container import TradeContainer

logger = logging.getLogger(__name__)


@dataclass
class PortfolioBundle:
    """
    Container bundle for one real portfolio + its WhatIf mirror.

    Real + WhatIf share positions, trades, risk factors.
    """
    config_name: str          # "tastytrade", "fidelity_ira", etc.
    currency: str             # "USD" or "INR"
    portfolio_ids: List[str] = field(default_factory=list)  # [real_id, whatif_id]

    portfolio: PortfolioContainer = field(default_factory=PortfolioContainer)
    positions: PositionContainer = field(default_factory=PositionContainer)
    risk_factors: RiskFactorContainer = field(default_factory=RiskFactorContainer)
    trades: TradeContainer = field(default_factory=TradeContainer)

    def add_portfolio_id(self, portfolio_id: str) -> None:
        """Register a portfolio ID (real or whatif) with this bundle."""
        if portfolio_id not in self.portfolio_ids:
            self.portfolio_ids.append(portfolio_id)

    def get_full_state(self) -> Dict[str, Any]:
        """Get complete state for this bundle (for UI/API)."""
        whatif_greeks = self.trades.aggregate_what_if_greeks()

        return {
            'config_name': self.config_name,
            'currency': self.currency,
            'portfolio_ids': self.portfolio_ids,
            'portfolio': self.portfolio.to_grid_row() if self.portfolio.state else {},
            'positions': self.positions.to_grid_rows(),
            'riskFactors': self.risk_factors.to_grid_rows(),
            'trades': self.trades.to_grid_rows(),
            'whatif_trades': self.trades.to_whatif_cards(),
            'whatif_portfolio': {
                'delta': float(whatif_greeks['delta']),
                'gamma': float(whatif_greeks['gamma']),
                'theta': float(whatif_greeks['theta']),
                'vega': float(whatif_greeks['vega']),
                'trade_count': self.trades.what_if_count,
            },
            'timestamp': datetime.utcnow().isoformat(),
        }
