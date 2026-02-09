"""
Position Container - In-memory holder for positions

Backed by PositionRepository, provides:
- Fast access to all positions
- Indexing by underlying for risk aggregation
- Change tracking at position/field level for cell updates
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """Current state of a single position"""
    position_id: str
    symbol: str
    underlying: str

    # Option specifics
    option_type: Optional[str] = None  # CALL, PUT, or None for stock
    strike: Optional[Decimal] = None
    expiry: Optional[str] = None
    dte: Optional[int] = None

    # Position
    quantity: int = 0

    # Prices
    entry_price: Decimal = Decimal('0')
    current_price: Decimal = Decimal('0')
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
    mark: Decimal = Decimal('0')

    # Greeks (position-level, already * quantity)
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    rho: Decimal = Decimal('0')
    iv: Decimal = Decimal('0')

    # P&L
    entry_value: Decimal = Decimal('0')
    market_value: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    unrealized_pnl_pct: Decimal = Decimal('0')

    # P&L Attribution
    pnl_delta: Decimal = Decimal('0')
    pnl_gamma: Decimal = Decimal('0')
    pnl_theta: Decimal = Decimal('0')
    pnl_vega: Decimal = Decimal('0')
    pnl_unexplained: Decimal = Decimal('0')

    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_option(self) -> bool:
        return self.option_type is not None

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def display_symbol(self) -> str:
        """Formatted symbol for display"""
        if self.is_option:
            ot = self.option_type[0] if self.option_type else '?'
            return f"{self.underlying} {self.expiry} {self.strike}{ot}"
        return self.symbol

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'underlying': self.underlying,
            'option_type': self.option_type,
            'strike': float(self.strike) if self.strike else None,
            'expiry': self.expiry,
            'dte': self.dte,
            'quantity': self.quantity,
            'entry_price': float(self.entry_price),
            'current_price': float(self.current_price),
            'bid': float(self.bid),
            'ask': float(self.ask),
            'mark': float(self.mark),
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
            'rho': float(self.rho),
            'iv': float(self.iv),
            'entry_value': float(self.entry_value),
            'market_value': float(self.market_value),
            'unrealized_pnl': float(self.unrealized_pnl),
            'unrealized_pnl_pct': float(self.unrealized_pnl_pct),
            'pnl_delta': float(self.pnl_delta),
            'pnl_gamma': float(self.pnl_gamma),
            'pnl_theta': float(self.pnl_theta),
            'pnl_vega': float(self.pnl_vega),
            'pnl_unexplained': float(self.pnl_unexplained),
            'last_updated': self.last_updated.isoformat(),
            'display_symbol': self.display_symbol,
            'is_option': self.is_option,
            'is_long': self.is_long,
        }


class PositionContainer:
    """
    In-memory container for positions.

    Design:
    - Holds all positions in memory as a dict keyed by position_id
    - Maintains index by underlying for fast risk aggregation
    - Tracks changes at position/field level for WebSocket push
    """

    def __init__(self):
        self._positions: Dict[str, PositionState] = {}
        self._by_underlying: Dict[str, List[str]] = {}  # underlying -> [position_ids]
        self._previous_states: Dict[str, Dict[str, Any]] = {}
        self._change_listeners: List[Callable] = []
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def count(self) -> int:
        return len(self._positions)

    @property
    def underlyings(self) -> List[str]:
        return list(self._by_underlying.keys())

    def add_change_listener(self, callback: Callable):
        """Add a listener for change events"""
        self._change_listeners.append(callback)

    def remove_change_listener(self, callback: Callable):
        """Remove a change listener"""
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_changes(self, position_id: str, changes: Dict[str, Any]):
        """Notify all listeners of changes"""
        for listener in self._change_listeners:
            try:
                listener('position', {'position_id': position_id, 'changes': changes})
            except Exception as e:
                logger.error(f"Error in change listener: {e}")

    def get(self, position_id: str) -> Optional[PositionState]:
        """Get a position by ID"""
        return self._positions.get(position_id)

    def get_by_underlying(self, underlying: str) -> List[PositionState]:
        """Get all positions for an underlying"""
        position_ids = self._by_underlying.get(underlying, [])
        return [self._positions[pid] for pid in position_ids if pid in self._positions]

    def get_all(self) -> List[PositionState]:
        """Get all positions"""
        return list(self._positions.values())

    def _rebuild_underlying_index(self):
        """Rebuild the underlying index from positions"""
        self._by_underlying.clear()
        for pid, pos in self._positions.items():
            if pos.underlying not in self._by_underlying:
                self._by_underlying[pos.underlying] = []
            self._by_underlying[pos.underlying].append(pid)

    def load_from_orm_list(self, positions_orm: List) -> Dict[str, Dict[str, Any]]:
        """
        Load positions from list of ORM objects.
        Returns dict of {position_id: changes} for WebSocket push.
        """
        # Capture previous states
        self._previous_states = {pid: pos.to_dict() for pid, pos in self._positions.items()}

        # Clear and reload
        self._positions.clear()

        for pos_orm in positions_orm:
            # Get symbol details from related symbol ORM
            symbol_orm = pos_orm.symbol if hasattr(pos_orm, 'symbol') else None

            underlying = symbol_orm.ticker if symbol_orm else 'UNKNOWN'
            option_type = symbol_orm.option_type.upper() if symbol_orm and symbol_orm.option_type else None
            strike = symbol_orm.strike if symbol_orm else None
            expiry = symbol_orm.expiration.strftime('%Y-%m-%d') if symbol_orm and symbol_orm.expiration else None

            # Calculate DTE
            dte = None
            if symbol_orm and symbol_orm.expiration:
                dte = (symbol_orm.expiration.date() - datetime.utcnow().date()).days

            state = PositionState(
                position_id=pos_orm.id,
                symbol=pos_orm.id,  # Will be overwritten if symbol_orm exists
                underlying=underlying,
                option_type=option_type,
                strike=Decimal(str(strike)) if strike else None,
                expiry=expiry,
                dte=dte,
                quantity=pos_orm.quantity,
                entry_price=pos_orm.entry_price or Decimal('0'),
                current_price=pos_orm.current_price or Decimal('0'),
                market_value=pos_orm.market_value or Decimal('0'),
                delta=pos_orm.delta or Decimal('0'),
                gamma=pos_orm.gamma or Decimal('0'),
                theta=pos_orm.theta or Decimal('0'),
                vega=pos_orm.vega or Decimal('0'),
                rho=pos_orm.rho or Decimal('0'),
                unrealized_pnl=pos_orm.total_pnl or Decimal('0'),
                pnl_delta=pos_orm.delta_pnl or Decimal('0'),
                pnl_gamma=pos_orm.gamma_pnl or Decimal('0'),
                pnl_theta=pos_orm.theta_pnl or Decimal('0'),
                pnl_vega=pos_orm.vega_pnl or Decimal('0'),
                pnl_unexplained=pos_orm.unexplained_pnl or Decimal('0'),
                last_updated=pos_orm.last_updated or datetime.utcnow(),
            )

            self._positions[pos_orm.id] = state

        self._rebuild_underlying_index()
        self._initialized = True

        # Detect all changes
        return self._detect_all_changes()

    def load_from_snapshot_positions(self, positions: List) -> Dict[str, Dict[str, Any]]:
        """
        Load from MarketSnapshot positions (PositionWithMarket objects).
        Returns dict of {position_id: changes}.
        """
        # Capture previous states
        self._previous_states = {pid: pos.to_dict() for pid, pos in self._positions.items()}

        # Clear and reload
        self._positions.clear()

        for pos in positions:
            position_id = getattr(pos, 'position_id', str(id(pos)))

            state = PositionState(
                position_id=position_id,
                symbol=pos.symbol,
                underlying=pos.symbol,  # Underlying is same as symbol for stocks
                option_type=pos.option_type,
                strike=pos.strike,
                expiry=pos.expiry,
                dte=pos.dte,
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                current_price=pos.last,
                bid=pos.bid,
                ask=pos.ask,
                mark=pos.mark,
                delta=pos.greeks.delta if pos.greeks else Decimal('0'),
                gamma=pos.greeks.gamma if pos.greeks else Decimal('0'),
                theta=pos.greeks.theta if pos.greeks else Decimal('0'),
                vega=pos.greeks.vega if pos.greeks else Decimal('0'),
                rho=pos.greeks.rho if pos.greeks else Decimal('0'),
                iv=pos.iv,
                entry_value=pos.entry_value,
                market_value=pos.market_value,
                unrealized_pnl=pos.unrealized_pnl,
                unrealized_pnl_pct=pos.unrealized_pnl_pct,
                pnl_delta=pos.pnl_from_delta,
                pnl_gamma=pos.pnl_from_gamma,
                pnl_theta=pos.pnl_from_theta,
                pnl_vega=pos.pnl_from_vega,
                pnl_unexplained=pos.pnl_unexplained,
                last_updated=datetime.utcnow(),
            )

            self._positions[position_id] = state

        self._rebuild_underlying_index()
        self._initialized = True

        return self._detect_all_changes()

    def _detect_all_changes(self) -> Dict[str, Dict[str, Any]]:
        """
        Detect changes for all positions.
        Returns {position_id: {field: {old, new}}}
        """
        all_changes = {}

        # Check existing positions for changes
        for pid, pos in self._positions.items():
            current = pos.to_dict()
            previous = self._previous_states.get(pid, {})

            changes = {}
            for key, new_value in current.items():
                old_value = previous.get(key)
                if old_value != new_value:
                    changes[key] = {'old': old_value, 'new': new_value}

            if changes:
                all_changes[pid] = changes
                self._notify_changes(pid, changes)

        # Check for removed positions
        for pid in self._previous_states:
            if pid not in self._positions:
                all_changes[pid] = {'_removed': True}

        return all_changes

    def update_position_field(self, position_id: str, field_name: str, value: Any) -> Dict[str, Any]:
        """Update a single field on a position"""
        pos = self._positions.get(position_id)
        if not pos:
            return {}

        old_value = getattr(pos, field_name, None)
        if old_value == value:
            return {}

        setattr(pos, field_name, value)
        pos.last_updated = datetime.utcnow()

        changes = {field_name: {'old': old_value, 'new': value}}
        self._notify_changes(position_id, changes)

        return changes

    def to_grid_rows(self) -> List[Dict[str, Any]]:
        """Convert all positions to AG Grid row format"""
        rows = []
        for pos in sorted(self._positions.values(),
                          key=lambda p: (p.underlying, p.expiry or '', float(p.strike or 0))):
            rows.append({
                'id': pos.position_id,
                'symbol': pos.display_symbol,
                'underlying': pos.underlying,
                'type': pos.option_type or 'STOCK',
                'strike': float(pos.strike) if pos.strike else None,
                'expiry': pos.expiry,
                'dte': pos.dte,
                'qty': pos.quantity,
                'entry': float(pos.entry_price),
                'mark': float(pos.mark),
                'bid': float(pos.bid),
                'ask': float(pos.ask),
                'delta': float(pos.delta),
                'gamma': float(pos.gamma),
                'theta': float(pos.theta),
                'vega': float(pos.vega),
                'iv': float(pos.iv) * 100 if pos.iv else None,  # Convert to percentage
                'pnl': float(pos.unrealized_pnl),
                'pnl_pct': float(pos.unrealized_pnl_pct),
                'pnl_delta': float(pos.pnl_delta),
                'pnl_theta': float(pos.pnl_theta),
                'pnl_vega': float(pos.pnl_vega),
            })
        return rows
