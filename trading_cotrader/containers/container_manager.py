"""
Container Manager - Orchestrates all containers and event distribution

Provides:
- Unified container management
- Event bus for container updates
- Cell-level change tracking for WebSocket push
- Repository integration for loading data
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional, Literal
from enum import Enum
import logging
import asyncio

from .portfolio_container import PortfolioContainer
from .position_container import PositionContainer
from .risk_factor_container import RiskFactorContainer
from .trade_container import TradeContainer

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of container events"""
    PORTFOLIO_UPDATE = "portfolio_update"
    POSITION_UPDATE = "position_update"
    POSITION_ADDED = "position_added"
    POSITION_REMOVED = "position_removed"
    RISK_FACTOR_UPDATE = "risk_factor_update"
    FULL_REFRESH = "full_refresh"
    CELL_UPDATE = "cell_update"


@dataclass
class CellUpdate:
    """Represents a single cell update for AG Grid"""
    grid_type: str  # 'portfolio', 'positions', 'risk_factors'
    row_id: str
    column: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'grid': self.grid_type,
            'rowId': self.row_id,
            'column': self.column,
            'oldValue': self.old_value,
            'newValue': self.new_value,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class ContainerEvent:
    """Event emitted when containers change"""
    event_type: EventType
    source: str  # Which container
    data: Dict[str, Any]
    cell_updates: List[CellUpdate] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'eventType': self.event_type.value,
            'source': self.source,
            'data': self.data,
            'cellUpdates': [cu.to_dict() for cu in self.cell_updates],
            'timestamp': self.timestamp.isoformat(),
        }


class ContainerManager:
    """
    Manages all containers and coordinates updates.

    Provides:
    - Single point of access to all containers
    - Event distribution for real-time updates
    - Cell-level change tracking for efficient UI updates
    - Integration with repositories for data loading
    """

    def __init__(self):
        self.portfolio = PortfolioContainer()
        self.positions = PositionContainer()
        self.risk_factors = RiskFactorContainer()
        self.trades = TradeContainer()  # Holds both real and what-if trades

        self._event_listeners: List[Callable] = []
        self._pending_cell_updates: List[CellUpdate] = []

        # Wire up internal change listeners
        self.portfolio.add_change_listener(self._on_portfolio_change)
        self.positions.add_change_listener(self._on_position_change)
        self.risk_factors.add_change_listener(self._on_risk_factor_change)
        self.trades.add_change_listener(self._on_trade_change)

    @property
    def is_initialized(self) -> bool:
        return self.portfolio.is_initialized

    def add_event_listener(self, callback: Callable):
        """Add listener for container events"""
        self._event_listeners.append(callback)

    def remove_event_listener(self, callback: Callable):
        """Remove event listener"""
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def _emit_event(self, event: ContainerEvent):
        """Emit event to all listeners"""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in event listener: {e}")

    def _on_portfolio_change(self, source: str, changes: Dict[str, Any]):
        """Handle portfolio container changes"""
        cell_updates = []
        for field_name, change in changes.items():
            cell_updates.append(CellUpdate(
                grid_type='portfolio',
                row_id='portfolio_summary',
                column=field_name,
                old_value=change.get('old'),
                new_value=change.get('new'),
            ))

        event = ContainerEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            source='portfolio',
            data=changes,
            cell_updates=cell_updates,
        )
        self._emit_event(event)

    def _on_position_change(self, source: str, data: Dict[str, Any]):
        """Handle position container changes"""
        position_id = data.get('position_id')
        changes = data.get('changes', {})

        cell_updates = []
        for field_name, change in changes.items():
            if field_name.startswith('_'):
                continue
            cell_updates.append(CellUpdate(
                grid_type='positions',
                row_id=position_id,
                column=field_name,
                old_value=change.get('old'),
                new_value=change.get('new'),
            ))

        event = ContainerEvent(
            event_type=EventType.POSITION_UPDATE,
            source='positions',
            data={'position_id': position_id, 'changes': changes},
            cell_updates=cell_updates,
        )
        self._emit_event(event)

    def _on_risk_factor_change(self, source: str, data: Dict[str, Any]):
        """Handle risk factor container changes"""
        underlying = data.get('underlying')
        changes = data.get('changes', {})

        cell_updates = []
        for field_name, change in changes.items():
            cell_updates.append(CellUpdate(
                grid_type='risk_factors',
                row_id=underlying,
                column=field_name,
                old_value=change.get('old'),
                new_value=change.get('new'),
            ))

        event = ContainerEvent(
            event_type=EventType.RISK_FACTOR_UPDATE,
            source='risk_factors',
            data={'underlying': underlying, 'changes': changes},
            cell_updates=cell_updates,
        )
        self._emit_event(event)

    def _on_trade_change(self, source: str, data: Dict[str, Any]):
        """Handle trade container changes"""
        trade_id = data.get('trade_id')
        changes = data.get('changes', {})

        cell_updates = []
        for field_name, change in changes.items():
            if field_name.startswith('_'):
                continue
            cell_updates.append(CellUpdate(
                grid_type='trades',
                row_id=trade_id,
                column=field_name,
                old_value=change.get('old') if isinstance(change, dict) else None,
                new_value=change.get('new') if isinstance(change, dict) else change,
            ))

        event = ContainerEvent(
            event_type=EventType.POSITION_UPDATE,  # Reuse for trades
            source='trades',
            data={'trade_id': trade_id, 'changes': changes},
            cell_updates=cell_updates,
        )
        self._emit_event(event)

    def load_from_repositories(self, session) -> ContainerEvent:
        """
        Load all containers from database repositories.
        Returns event with all changes.
        """
        from trading_cotrader.repositories.portfolio import PortfolioRepository
        from trading_cotrader.core.database.schema import PositionORM

        all_cell_updates = []

        # Load portfolio
        portfolio_repo = PortfolioRepository(session)
        portfolios = session.query(portfolio_repo.model_class).all()
        if portfolios:
            portfolio_orm = portfolios[0]  # Use first portfolio
            changes = self.portfolio.load_from_orm(portfolio_orm)
            for field_name, change in changes.items():
                all_cell_updates.append(CellUpdate(
                    grid_type='portfolio',
                    row_id='portfolio_summary',
                    column=field_name,
                    old_value=change.get('old'),
                    new_value=change.get('new'),
                ))

        # Load positions
        positions_orm = session.query(PositionORM).all()
        pos_changes = self.positions.load_from_orm_list(positions_orm)
        for pos_id, changes in pos_changes.items():
            for field_name, change in changes.items():
                if field_name.startswith('_'):
                    continue
                all_cell_updates.append(CellUpdate(
                    grid_type='positions',
                    row_id=pos_id,
                    column=field_name,
                    old_value=change.get('old'),
                    new_value=change.get('new'),
                ))

        # Aggregate risk factors from positions
        rf_changes = self.risk_factors.aggregate_from_positions(self.positions)
        for underlying, changes in rf_changes.items():
            for field_name, change in changes.items():
                all_cell_updates.append(CellUpdate(
                    grid_type='risk_factors',
                    row_id=underlying,
                    column=field_name,
                    old_value=change.get('old'),
                    new_value=change.get('new'),
                ))

        event = ContainerEvent(
            event_type=EventType.FULL_REFRESH,
            source='repository',
            data={'positions_count': self.positions.count},
            cell_updates=all_cell_updates,
        )

        return event

    def load_from_snapshot(self, snapshot) -> ContainerEvent:
        """
        Load all containers from a MarketSnapshot.
        For compatibility with existing data provider.
        """
        all_cell_updates = []

        # Load portfolio from snapshot
        changes = self.portfolio.load_from_snapshot(snapshot)
        for field_name, change in changes.items():
            all_cell_updates.append(CellUpdate(
                grid_type='portfolio',
                row_id='portfolio_summary',
                column=field_name,
                old_value=change.get('old'),
                new_value=change.get('new'),
            ))

        # Load positions
        positions = getattr(snapshot, 'positions', [])
        pos_changes = self.positions.load_from_snapshot_positions(positions)
        for pos_id, changes in pos_changes.items():
            for field_name, change in changes.items():
                if field_name.startswith('_'):
                    continue
                all_cell_updates.append(CellUpdate(
                    grid_type='positions',
                    row_id=pos_id,
                    column=field_name,
                    old_value=change.get('old'),
                    new_value=change.get('new'),
                ))

        # Load risk factors
        risk_by_underlying = getattr(snapshot, 'risk_by_underlying', {})
        rf_changes = self.risk_factors.load_from_snapshot_risk(risk_by_underlying)
        for underlying, changes in rf_changes.items():
            for field_name, change in changes.items():
                all_cell_updates.append(CellUpdate(
                    grid_type='risk_factors',
                    row_id=underlying,
                    column=field_name,
                    old_value=change.get('old'),
                    new_value=change.get('new'),
                ))

        event = ContainerEvent(
            event_type=EventType.FULL_REFRESH,
            source='snapshot',
            data={'positions_count': self.positions.count},
            cell_updates=all_cell_updates,
        )

        return event

    def get_full_state(self) -> Dict[str, Any]:
        """Get complete current state for initial load"""
        whatif_greeks = self.trades.aggregate_what_if_greeks()

        return {
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

    def refresh(self, session=None, snapshot=None) -> ContainerEvent:
        """
        Refresh all containers.
        Either from repository (session) or snapshot.
        """
        if session:
            return self.load_from_repositories(session)
        elif snapshot:
            return self.load_from_snapshot(snapshot)
        else:
            # Return empty event if no data source
            return ContainerEvent(
                event_type=EventType.FULL_REFRESH,
                source='none',
                data={},
                cell_updates=[],
            )
