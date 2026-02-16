"""
Container Manager - Orchestrates per-portfolio container bundles and event distribution

Provides:
- Per-portfolio container bundles (real + whatif share a bundle)
- Event bus for container updates
- Cell-level change tracking for WebSocket push
- Repository integration for loading data
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional
from enum import Enum
import logging

from .portfolio_container import PortfolioContainer
from .position_container import PositionContainer
from .risk_factor_container import RiskFactorContainer
from .trade_container import TradeContainer
from .portfolio_bundle import PortfolioBundle

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
    Manages per-portfolio container bundles and coordinates updates.

    Each real portfolio (+ its WhatIf mirror) gets one PortfolioBundle.
    Bundles are currency-isolated: USD positions never mix with INR.

    Backward compatibility:
    - .portfolio, .positions, .risk_factors, .trades still work (default bundle)
    - get_full_state() without args returns default bundle
    """

    def __init__(self):
        self._bundles: Dict[str, PortfolioBundle] = {}
        # Maps whatif config_name → real config_name for bundle lookup
        self._whatif_to_real: Dict[str, str] = {}

        self._event_listeners: List[Callable] = []

        # Default bundle name (first real portfolio initialized)
        self._default_bundle: Optional[str] = None

    # -----------------------------------------------------------------
    # Bundle initialization
    # -----------------------------------------------------------------

    def initialize_bundles(self, portfolios_config) -> None:
        """
        Create one bundle per REAL portfolio. WhatIf shares parent's bundle.

        Args:
            portfolios_config: PortfoliosConfig from risk_config_loader
        """
        from trading_cotrader.config.risk_config_loader import PortfoliosConfig

        for pc in portfolios_config.get_real_portfolios():
            bundle = PortfolioBundle(
                config_name=pc.name,
                currency=pc.currency,
            )
            self._bundles[pc.name] = bundle
            if self._default_bundle is None:
                self._default_bundle = pc.name
            logger.info(f"Created bundle: {pc.name} ({pc.currency})")

        # Map whatif → real parent
        for pc in portfolios_config.get_whatif_portfolios():
            if pc.mirrors_real and pc.mirrors_real in self._bundles:
                self._whatif_to_real[pc.name] = pc.mirrors_real
                logger.debug(f"WhatIf {pc.name} → bundle {pc.mirrors_real}")

        logger.info(f"Initialized {len(self._bundles)} portfolio bundles")

    # -----------------------------------------------------------------
    # Bundle access
    # -----------------------------------------------------------------

    def get_bundle(self, config_name: str) -> Optional[PortfolioBundle]:
        """
        Get bundle by config name. Resolves whatif names to parent bundle.
        """
        # Direct lookup
        if config_name in self._bundles:
            return self._bundles[config_name]
        # WhatIf → parent
        real_name = self._whatif_to_real.get(config_name)
        if real_name:
            return self._bundles.get(real_name)
        return None

    def get_all_bundles(self) -> List[PortfolioBundle]:
        """Get all portfolio bundles."""
        return list(self._bundles.values())

    def get_bundles_by_currency(self, currency: str) -> List[PortfolioBundle]:
        """Get bundles filtered by currency."""
        return [b for b in self._bundles.values() if b.currency == currency]

    def get_bundle_names(self) -> List[str]:
        """Get all bundle config names."""
        return list(self._bundles.keys())

    # -----------------------------------------------------------------
    # Backward compatibility: default bundle properties
    # -----------------------------------------------------------------

    @property
    def _default(self) -> Optional[PortfolioBundle]:
        """Get the default bundle (first real portfolio)."""
        if self._default_bundle:
            return self._bundles.get(self._default_bundle)
        if self._bundles:
            return next(iter(self._bundles.values()))
        return None

    @property
    def portfolio(self) -> PortfolioContainer:
        b = self._default
        if b:
            return b.portfolio
        # Fallback: create empty container
        if not hasattr(self, '_fallback_portfolio'):
            self._fallback_portfolio = PortfolioContainer()
        return self._fallback_portfolio

    @property
    def positions(self) -> PositionContainer:
        b = self._default
        if b:
            return b.positions
        if not hasattr(self, '_fallback_positions'):
            self._fallback_positions = PositionContainer()
        return self._fallback_positions

    @property
    def risk_factors(self) -> RiskFactorContainer:
        b = self._default
        if b:
            return b.risk_factors
        if not hasattr(self, '_fallback_risk_factors'):
            self._fallback_risk_factors = RiskFactorContainer()
        return self._fallback_risk_factors

    @property
    def trades(self) -> TradeContainer:
        b = self._default
        if b:
            return b.trades
        if not hasattr(self, '_fallback_trades'):
            self._fallback_trades = TradeContainer()
        return self._fallback_trades

    @property
    def is_initialized(self) -> bool:
        b = self._default
        return b.portfolio.is_initialized if b else False

    # -----------------------------------------------------------------
    # Event handling
    # -----------------------------------------------------------------

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

    # -----------------------------------------------------------------
    # Data loading — per-portfolio
    # -----------------------------------------------------------------

    def load_from_repositories(self, session, portfolio_name: str = None) -> ContainerEvent:
        """
        Load containers from database repositories.

        If portfolio_name is given, loads only that bundle.
        Otherwise loads the default bundle (backward compat).

        Returns event with all changes.
        """
        from trading_cotrader.repositories.portfolio import PortfolioRepository
        from trading_cotrader.core.database.schema import PositionORM, PortfolioORM

        target_name = portfolio_name or self._default_bundle
        bundle = self.get_bundle(target_name) if target_name else self._default

        if not bundle:
            logger.warning(f"No bundle found for '{target_name}'")
            return ContainerEvent(
                event_type=EventType.FULL_REFRESH,
                source='repository',
                data={},
                cell_updates=[],
            )

        all_cell_updates: List[CellUpdate] = []

        # Load portfolio ORM — filter by portfolio IDs in this bundle
        if bundle.portfolio_ids:
            portfolio_orm = session.query(PortfolioORM).filter(
                PortfolioORM.id.in_(bundle.portfolio_ids)
            ).first()
        else:
            # Fallback: query by broker+account from config
            portfolio_repo = PortfolioRepository(session)
            portfolios = portfolio_repo.get_all_portfolios()
            portfolio_orm = None
            if portfolios:
                # Find by name match
                for p in portfolios:
                    p_orm = session.query(PortfolioORM).filter_by(id=p.id).first()
                    if p_orm:
                        portfolio_orm = p_orm
                        bundle.add_portfolio_id(p.id)
                        break

        if portfolio_orm:
            changes = bundle.portfolio.load_from_orm(portfolio_orm)
            for field_name, change in changes.items():
                all_cell_updates.append(CellUpdate(
                    grid_type='portfolio',
                    row_id='portfolio_summary',
                    column=field_name,
                    old_value=change.get('old'),
                    new_value=change.get('new'),
                ))

        # Load positions — filtered by portfolio IDs in this bundle
        if bundle.portfolio_ids:
            positions_orm = session.query(PositionORM).filter(
                PositionORM.portfolio_id.in_(bundle.portfolio_ids)
            ).all()
        else:
            positions_orm = session.query(PositionORM).all()

        pos_changes = bundle.positions.load_from_orm_list(positions_orm)
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

        # Aggregate risk factors from filtered positions
        rf_changes = bundle.risk_factors.aggregate_from_positions(bundle.positions)
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
            data={
                'portfolio_name': bundle.config_name,
                'positions_count': bundle.positions.count,
            },
            cell_updates=all_cell_updates,
        )

        self._emit_event(event)
        return event

    def load_all_bundles(self, session) -> None:
        """Load all bundles from repositories."""
        for name in self._bundles:
            self.load_from_repositories(session, portfolio_name=name)

    def load_from_snapshot(self, snapshot) -> ContainerEvent:
        """
        Load default bundle from a MarketSnapshot.
        For compatibility with existing data provider.
        """
        bundle = self._default
        if not bundle:
            # Create a temporary default bundle
            bundle = PortfolioBundle(config_name="default", currency="USD")
            self._bundles["default"] = bundle
            self._default_bundle = "default"

        all_cell_updates: List[CellUpdate] = []

        # Load portfolio from snapshot
        changes = bundle.portfolio.load_from_snapshot(snapshot)
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
        pos_changes = bundle.positions.load_from_snapshot_positions(positions)
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
        rf_changes = bundle.risk_factors.load_from_snapshot_risk(risk_by_underlying)
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
            data={'positions_count': bundle.positions.count},
            cell_updates=all_cell_updates,
        )

        return event

    # -----------------------------------------------------------------
    # State access
    # -----------------------------------------------------------------

    def get_full_state(self, config_name: str = None) -> Dict[str, Any]:
        """
        Get complete current state.

        Args:
            config_name: Portfolio bundle name. None = default bundle.

        Returns:
            Full state dict for UI/API.
        """
        if config_name:
            bundle = self.get_bundle(config_name)
        else:
            bundle = self._default

        if bundle:
            return bundle.get_full_state()

        # Empty state fallback
        return {
            'portfolio': {},
            'positions': [],
            'riskFactors': [],
            'trades': [],
            'whatif_trades': [],
            'whatif_portfolio': {
                'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0,
                'trade_count': 0,
            },
            'timestamp': datetime.utcnow().isoformat(),
        }

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get full state for all bundles."""
        return {name: bundle.get_full_state() for name, bundle in self._bundles.items()}

    def refresh(self, session=None, snapshot=None, portfolio_name: str = None) -> ContainerEvent:
        """
        Refresh containers. Either from repository (session) or snapshot.
        """
        if session:
            return self.load_from_repositories(session, portfolio_name=portfolio_name)
        elif snapshot:
            return self.load_from_snapshot(snapshot)
        else:
            return ContainerEvent(
                event_type=EventType.FULL_REFRESH,
                source='none',
                data={},
                cell_updates=[],
            )
