"""
In-Memory Containers

These containers are in-memory holders of ORM data from repositories.
They provide:
1. Fast access to current state (no DB round-trips)
2. Event-driven updates (container refreshes on events)
3. Cell-level change tracking for WebSocket push

Design:
- Containers load data from repositories on init/refresh
- Changes are tracked at the field level for efficient UI updates
- Containers emit events when data changes
"""

from .portfolio_container import PortfolioContainer
from .position_container import PositionContainer
from .risk_factor_container import RiskFactorContainer
from .trade_container import TradeContainer
from .portfolio_bundle import PortfolioBundle
from .container_manager import ContainerManager, CellUpdate, ContainerEvent

__all__ = [
    'PortfolioContainer',
    'PositionContainer',
    'RiskFactorContainer',
    'TradeContainer',
    'PortfolioBundle',
    'ContainerManager',
    'CellUpdate',
    'ContainerEvent',
]
