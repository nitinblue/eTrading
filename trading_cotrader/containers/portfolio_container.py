"""
Portfolio Container - In-memory holder for portfolio data

Backed by PortfolioRepository, provides:
- Fast access to portfolio state
- Change tracking for cell-level updates
- Event emission on changes
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class PortfolioState:
    """Current state of a portfolio"""
    portfolio_id: str
    name: str
    portfolio_type: str = "real"

    # Capital
    total_equity: Decimal = Decimal('0')
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')

    # Greeks
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    rho: Decimal = Decimal('0')

    # P&L
    total_pnl: Decimal = Decimal('0')
    daily_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')

    # Risk metrics
    var_1d_95: Decimal = Decimal('0')
    position_count: int = 0

    # Risk status
    risk_status: str = "OK"

    # Limits
    max_delta: Decimal = Decimal('500')
    max_gamma: Decimal = Decimal('50')
    min_theta: Decimal = Decimal('-500')
    max_vega: Decimal = Decimal('1000')

    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'portfolio_id': self.portfolio_id,
            'name': self.name,
            'portfolio_type': self.portfolio_type,
            'total_equity': float(self.total_equity),
            'cash_balance': float(self.cash_balance),
            'buying_power': float(self.buying_power),
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
            'rho': float(self.rho),
            'total_pnl': float(self.total_pnl),
            'daily_pnl': float(self.daily_pnl),
            'realized_pnl': float(self.realized_pnl),
            'unrealized_pnl': float(self.unrealized_pnl),
            'var_1d_95': float(self.var_1d_95),
            'position_count': self.position_count,
            'risk_status': self.risk_status,
            'max_delta': float(self.max_delta),
            'max_gamma': float(self.max_gamma),
            'min_theta': float(self.min_theta),
            'max_vega': float(self.max_vega),
            'last_updated': self.last_updated.isoformat(),
        }


class PortfolioContainer:
    """
    In-memory container for portfolio state.

    Design:
    - Holds current portfolio state in memory
    - Tracks changes at field level for efficient WebSocket push
    - Loads from repository on init/refresh
    - Emits events when fields change
    """

    def __init__(self):
        self._state: Optional[PortfolioState] = None
        self._previous_state: Optional[Dict[str, Any]] = None
        self._change_listeners: List[Callable] = []
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized and self._state is not None

    @property
    def state(self) -> Optional[PortfolioState]:
        return self._state

    def add_change_listener(self, callback: Callable):
        """Add a listener for change events"""
        self._change_listeners.append(callback)

    def remove_change_listener(self, callback: Callable):
        """Remove a change listener"""
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_changes(self, changes: Dict[str, Any]):
        """Notify all listeners of changes"""
        for listener in self._change_listeners:
            try:
                listener('portfolio', changes)
            except Exception as e:
                logger.error(f"Error in change listener: {e}")

    def load_from_orm(self, portfolio_orm) -> Dict[str, Any]:
        """
        Load portfolio state from ORM object.
        Returns dict of changed fields for WebSocket push.
        """
        if portfolio_orm is None:
            return {}

        # Capture previous state for change detection
        if self._state:
            self._previous_state = self._state.to_dict()

        # Create new state from ORM
        self._state = PortfolioState(
            portfolio_id=portfolio_orm.id,
            name=portfolio_orm.name,
            portfolio_type=portfolio_orm.portfolio_type or 'real',
            total_equity=portfolio_orm.total_equity or Decimal('0'),
            cash_balance=portfolio_orm.cash_balance or Decimal('0'),
            buying_power=portfolio_orm.buying_power or Decimal('0'),
            delta=portfolio_orm.portfolio_delta or Decimal('0'),
            gamma=portfolio_orm.portfolio_gamma or Decimal('0'),
            theta=portfolio_orm.portfolio_theta or Decimal('0'),
            vega=portfolio_orm.portfolio_vega or Decimal('0'),
            rho=portfolio_orm.portfolio_rho or Decimal('0'),
            total_pnl=portfolio_orm.total_pnl or Decimal('0'),
            daily_pnl=portfolio_orm.daily_pnl or Decimal('0'),
            realized_pnl=portfolio_orm.realized_pnl or Decimal('0'),
            unrealized_pnl=portfolio_orm.unrealized_pnl or Decimal('0'),
            var_1d_95=portfolio_orm.var_1d_95 or Decimal('0'),
            max_delta=portfolio_orm.max_portfolio_delta or Decimal('500'),
            max_gamma=portfolio_orm.max_portfolio_gamma or Decimal('50'),
            min_theta=portfolio_orm.min_portfolio_theta or Decimal('-500'),
            max_vega=portfolio_orm.max_portfolio_vega or Decimal('1000'),
            last_updated=portfolio_orm.last_updated or datetime.utcnow(),
        )

        # Compute risk status
        self._state.risk_status = self._compute_risk_status()

        self._initialized = True

        # Detect changes
        changes = self._detect_changes()
        if changes:
            self._notify_changes(changes)

        return changes

    def load_from_snapshot(self, snapshot) -> Dict[str, Any]:
        """
        Load from a MarketSnapshot (for compatibility with existing code).
        Returns dict of changed fields.
        """
        if snapshot is None:
            return {}

        # Capture previous state
        if self._state:
            self._previous_state = self._state.to_dict()

        # Extract portfolio risk from snapshot
        portfolio_risk = getattr(snapshot, 'portfolio_risk', None)

        self._state = PortfolioState(
            portfolio_id=getattr(snapshot, 'portfolio_id', 'default'),
            name=getattr(snapshot, 'portfolio_name', 'Trading Portfolio'),
            total_equity=getattr(snapshot, 'account_value', Decimal('0')),
            buying_power=getattr(snapshot, 'buying_power', Decimal('0')),
            delta=portfolio_risk.delta if portfolio_risk else Decimal('0'),
            gamma=portfolio_risk.gamma if portfolio_risk else Decimal('0'),
            theta=portfolio_risk.theta if portfolio_risk else Decimal('0'),
            vega=portfolio_risk.vega if portfolio_risk else Decimal('0'),
            position_count=portfolio_risk.position_count if portfolio_risk else 0,
            last_updated=snapshot.timestamp,
        )

        # Compute risk status from breaches
        breaches = getattr(snapshot, 'breaches', [])
        if any(getattr(b, 'severity', '') == 'critical' for b in breaches):
            self._state.risk_status = "CRITICAL"
        elif any(getattr(b, 'severity', '') == 'breach' for b in breaches):
            self._state.risk_status = "WARNING"
        else:
            self._state.risk_status = "OK"

        self._initialized = True

        # Detect changes
        changes = self._detect_changes()
        if changes:
            self._notify_changes(changes)

        return changes

    def _compute_risk_status(self) -> str:
        """Compute risk status from current state vs limits"""
        if not self._state:
            return "OK"

        s = self._state

        # Check limit breaches
        if abs(s.delta) > abs(s.max_delta):
            return "CRITICAL" if abs(s.delta) > abs(s.max_delta) * Decimal('1.5') else "WARNING"
        if abs(s.gamma) > abs(s.max_gamma):
            return "CRITICAL" if abs(s.gamma) > abs(s.max_gamma) * Decimal('1.5') else "WARNING"
        if s.theta < s.min_theta:
            return "WARNING"
        if abs(s.vega) > abs(s.max_vega):
            return "WARNING"

        return "OK"

    def _detect_changes(self) -> Dict[str, Any]:
        """
        Detect which fields changed from previous state.
        Returns dict of {field_name: {'old': old_value, 'new': new_value}}
        """
        if not self._previous_state or not self._state:
            # First load - all fields are "new"
            if self._state:
                return {k: {'old': None, 'new': v} for k, v in self._state.to_dict().items()}
            return {}

        changes = {}
        current = self._state.to_dict()

        for key, new_value in current.items():
            old_value = self._previous_state.get(key)
            if old_value != new_value:
                changes[key] = {'old': old_value, 'new': new_value}

        return changes

    def update_field(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Update a single field and return change info.
        Used for incremental updates.
        """
        if not self._state:
            return {}

        old_value = getattr(self._state, field_name, None)
        if old_value == value:
            return {}

        setattr(self._state, field_name, value)
        self._state.last_updated = datetime.utcnow()

        changes = {field_name: {'old': old_value, 'new': value}}
        self._notify_changes(changes)

        return changes

    def on_trade_booked(self, delta: Decimal, theta: Decimal) -> Dict[str, Any]:
        """Handle trade booking event - updates Greeks incrementally"""
        if not self._state:
            return {}

        old_delta = self._state.delta
        old_theta = self._state.theta
        old_count = self._state.position_count

        self._state.delta += delta
        self._state.theta += theta
        self._state.position_count += 1
        self._state.risk_status = self._compute_risk_status()
        self._state.last_updated = datetime.utcnow()

        changes = {
            'delta': {'old': float(old_delta), 'new': float(self._state.delta)},
            'theta': {'old': float(old_theta), 'new': float(self._state.theta)},
            'position_count': {'old': old_count, 'new': self._state.position_count},
        }

        self._notify_changes(changes)
        return changes

    def to_grid_row(self) -> Dict[str, Any]:
        """Convert to AG Grid row format"""
        if not self._state:
            return {}

        return {
            'id': 'portfolio_summary',
            'metric': 'Portfolio Summary',
            'total_equity': float(self._state.total_equity),
            'cash_balance': float(self._state.cash_balance),
            'buying_power': float(self._state.buying_power),
            'delta': float(self._state.delta),
            'gamma': float(self._state.gamma),
            'theta': float(self._state.theta),
            'vega': float(self._state.vega),
            'position_count': self._state.position_count,
            'risk_status': self._state.risk_status,
            'pnl': float(self._state.total_pnl),
            'daily_pnl': float(self._state.daily_pnl),
        }
