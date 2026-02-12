"""
Trade Container - In-memory holder for trades (especially what-if trades)

Provides:
- Fast access to all trades by ID
- Filtering by trade type (real, what_if)
- Aggregated Greeks for what-if trades
- Change tracking for WebSocket push
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class LegState:
    """State of a single trade leg"""
    leg_id: str
    symbol: str
    underlying: str
    option_type: Optional[str] = None  # CALL, PUT, or None
    strike: Optional[Decimal] = None
    expiry: Optional[str] = None
    quantity: int = 0
    side: str = ""  # buy, sell, buy_to_open, sell_to_open, etc.
    entry_price: Decimal = Decimal('0')
    current_price: Decimal = Decimal('0')

    # Greeks (per contract)
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'leg_id': self.leg_id,
            'symbol': self.symbol,
            'underlying': self.underlying,
            'option_type': self.option_type,
            'strike': float(self.strike) if self.strike else None,
            'expiry': self.expiry,
            'quantity': self.quantity,
            'side': self.side,
            'entry_price': float(self.entry_price),
            'current_price': float(self.current_price),
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
        }

    @property
    def is_long(self) -> bool:
        return self.quantity > 0 or 'buy' in self.side.lower()

    @property
    def is_short(self) -> bool:
        return self.quantity < 0 or 'sell' in self.side.lower()

    @property
    def position_delta(self) -> Decimal:
        """Delta adjusted for position direction"""
        multiplier = -1 if self.is_short else 1
        return self.delta * abs(self.quantity) * multiplier * 100  # 100 multiplier for options

    @property
    def position_theta(self) -> Decimal:
        """Theta adjusted for position direction"""
        multiplier = -1 if self.is_short else 1
        return self.theta * abs(self.quantity) * multiplier * 100

    @property
    def position_vega(self) -> Decimal:
        """Vega adjusted for position direction"""
        multiplier = -1 if self.is_short else 1
        return self.vega * abs(self.quantity) * multiplier * 100


@dataclass
class TradeState:
    """Current state of a trade"""
    trade_id: str
    underlying: str
    trade_type: str = "what_if"  # real, paper, what_if, backtest
    trade_status: str = "intent"  # intent, evaluated, pending, executed, closed
    strategy_type: str = "custom"

    legs: List[LegState] = field(default_factory=list)

    # Pricing
    entry_price: Decimal = Decimal('0')  # Net debit/credit
    current_price: Decimal = Decimal('0')

    # Aggregated Greeks
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')

    # Risk metrics
    max_profit: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    breakeven_points: List[Decimal] = field(default_factory=list)

    # Metadata
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def calculate_greeks(self):
        """Aggregate Greeks from all legs"""
        self.delta = sum(leg.position_delta for leg in self.legs)
        self.gamma = sum(Decimal(str(leg.gamma)) * abs(leg.quantity) * 100 for leg in self.legs)
        self.theta = sum(leg.position_theta for leg in self.legs)
        self.vega = sum(leg.position_vega for leg in self.legs)

    @property
    def is_what_if(self) -> bool:
        return self.trade_type == "what_if"

    @property
    def is_real(self) -> bool:
        return self.trade_type == "real"

    @property
    def is_open(self) -> bool:
        return self.trade_status in ["executed", "partial"]

    @property
    def legs_count(self) -> int:
        return len(self.legs)

    @property
    def dte(self) -> Optional[int]:
        """Days to earliest expiration"""
        dtes = []
        for leg in self.legs:
            if leg.expiry:
                try:
                    exp_date = datetime.strptime(leg.expiry, "%Y-%m-%d").date()
                    dte = (exp_date - datetime.utcnow().date()).days
                    dtes.append(dte)
                except:
                    pass
        return min(dtes) if dtes else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'underlying': self.underlying,
            'trade_type': self.trade_type,
            'trade_status': self.trade_status,
            'strategy_type': self.strategy_type,
            'legs': [leg.to_dict() for leg in self.legs],
            'legs_count': self.legs_count,
            'entry_price': float(self.entry_price),
            'current_price': float(self.current_price),
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
            'max_profit': float(self.max_profit) if self.max_profit else None,
            'max_loss': float(self.max_loss) if self.max_loss else None,
            'breakeven_points': [float(bp) for bp in self.breakeven_points],
            'dte': self.dte,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
        }


class TradeContainer:
    """
    In-memory container for trades.

    Design:
    - Holds all trades in memory as a dict keyed by trade_id
    - Separate views for real vs what-if trades
    - Change tracking at trade/field level for WebSocket push
    """

    def __init__(self):
        self._trades: Dict[str, TradeState] = {}
        self._previous_states: Dict[str, Dict[str, Any]] = {}
        self._change_listeners: List[Callable] = []
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def count(self) -> int:
        return len(self._trades)

    @property
    def what_if_count(self) -> int:
        return sum(1 for t in self._trades.values() if t.is_what_if)

    @property
    def real_count(self) -> int:
        return sum(1 for t in self._trades.values() if t.is_real)

    def add_change_listener(self, callback: Callable):
        """Add a listener for change events"""
        self._change_listeners.append(callback)

    def remove_change_listener(self, callback: Callable):
        """Remove a change listener"""
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_changes(self, trade_id: str, changes: Dict[str, Any]):
        """Notify all listeners of changes"""
        for listener in self._change_listeners:
            try:
                listener('trade', {'trade_id': trade_id, 'changes': changes})
            except Exception as e:
                logger.error(f"Error in change listener: {e}")

    def get(self, trade_id: str) -> Optional[TradeState]:
        """Get a trade by ID"""
        return self._trades.get(trade_id)

    def get_all(self) -> List[TradeState]:
        """Get all trades"""
        return list(self._trades.values())

    def get_what_if_trades(self) -> List[TradeState]:
        """Get only what-if trades"""
        return [t for t in self._trades.values() if t.is_what_if]

    def get_real_trades(self) -> List[TradeState]:
        """Get only real trades"""
        return [t for t in self._trades.values() if t.is_real]

    def get_by_underlying(self, underlying: str) -> List[TradeState]:
        """Get all trades for an underlying"""
        return [t for t in self._trades.values() if t.underlying == underlying]

    def add_trade(self, trade: TradeState) -> Dict[str, Any]:
        """
        Add a new trade.
        Returns changes dict.
        """
        self._trades[trade.trade_id] = trade
        trade.calculate_greeks()

        changes = {'_added': True, **trade.to_dict()}
        self._notify_changes(trade.trade_id, changes)

        return changes

    def create_what_if_trade(
        self,
        underlying: str,
        strategy_type: str,
        legs: List[Dict[str, Any]],
        notes: str = ""
    ) -> TradeState:
        """
        Create a new what-if trade from leg definitions.

        legs: List of dicts with keys:
            - option_type: 'CALL' or 'PUT'
            - strike: Decimal
            - expiry: str (YYYY-MM-DD)
            - quantity: int (positive = long, negative = short)
            - side: 'buy' or 'sell'
            - delta, gamma, theta, vega: Decimal (per contract)
            - entry_price: Decimal
        """
        trade_id = str(uuid.uuid4())

        leg_states = []
        for i, leg_def in enumerate(legs):
            leg = LegState(
                leg_id=f"{trade_id}_leg_{i}",
                symbol=f"{underlying} {leg_def.get('expiry', '')} {leg_def.get('strike', '')} {leg_def.get('option_type', '')[0] if leg_def.get('option_type') else ''}",
                underlying=underlying,
                option_type=leg_def.get('option_type'),
                strike=Decimal(str(leg_def.get('strike', 0))),
                expiry=leg_def.get('expiry'),
                quantity=leg_def.get('quantity', 1),
                side=leg_def.get('side', 'buy'),
                entry_price=Decimal(str(leg_def.get('entry_price', 0))),
                current_price=Decimal(str(leg_def.get('current_price', leg_def.get('entry_price', 0)))),
                delta=Decimal(str(leg_def.get('delta', 0))),
                gamma=Decimal(str(leg_def.get('gamma', 0))),
                theta=Decimal(str(leg_def.get('theta', 0))),
                vega=Decimal(str(leg_def.get('vega', 0))),
            )
            leg_states.append(leg)

        trade = TradeState(
            trade_id=trade_id,
            underlying=underlying,
            trade_type="what_if",
            trade_status="intent",
            strategy_type=strategy_type,
            legs=leg_states,
            notes=notes,
        )

        trade.calculate_greeks()

        self.add_trade(trade)
        self._initialized = True

        return trade

    def remove_trade(self, trade_id: str) -> bool:
        """Remove a trade"""
        if trade_id not in self._trades:
            return False

        del self._trades[trade_id]
        self._notify_changes(trade_id, {'_removed': True})

        return True

    def update_trade_status(self, trade_id: str, new_status: str) -> Dict[str, Any]:
        """Update trade status"""
        trade = self._trades.get(trade_id)
        if not trade:
            return {}

        old_status = trade.trade_status
        trade.trade_status = new_status
        trade.last_updated = datetime.utcnow()

        changes = {'trade_status': {'old': old_status, 'new': new_status}}
        self._notify_changes(trade_id, changes)

        return changes

    def convert_to_real(self, trade_id: str) -> Optional[TradeState]:
        """
        Convert a what-if trade to a real trade.
        Changes trade_type and resets status to 'intent'.
        """
        trade = self._trades.get(trade_id)
        if not trade or not trade.is_what_if:
            return None

        trade.trade_type = "real"
        trade.trade_status = "intent"
        trade.last_updated = datetime.utcnow()

        changes = {
            'trade_type': {'old': 'what_if', 'new': 'real'},
            'trade_status': {'old': trade.trade_status, 'new': 'intent'},
        }
        self._notify_changes(trade_id, changes)

        return trade

    def aggregate_what_if_greeks(self) -> Dict[str, Decimal]:
        """
        Aggregate Greeks across all what-if trades.
        Returns dict with delta, gamma, theta, vega totals.
        """
        totals = {
            'delta': Decimal('0'),
            'gamma': Decimal('0'),
            'theta': Decimal('0'),
            'vega': Decimal('0'),
        }

        for trade in self.get_what_if_trades():
            totals['delta'] += trade.delta
            totals['gamma'] += trade.gamma
            totals['theta'] += trade.theta
            totals['vega'] += trade.vega

        return totals

    def load_from_orm_list(self, trades_orm: List) -> Dict[str, Dict[str, Any]]:
        """
        Load trades from list of ORM objects.
        Returns dict of {trade_id: changes}.
        """
        self._previous_states = {tid: trade.to_dict() for tid, trade in self._trades.items()}
        self._trades.clear()

        for trade_orm in trades_orm:
            legs = []
            for leg_orm in getattr(trade_orm, 'legs', []):
                symbol_orm = getattr(leg_orm, 'symbol', None)
                legs.append(LegState(
                    leg_id=leg_orm.id,
                    symbol=f"{symbol_orm.ticker if symbol_orm else ''} {symbol_orm.expiration.strftime('%Y-%m-%d') if symbol_orm and symbol_orm.expiration else ''} {symbol_orm.strike if symbol_orm else ''} {(symbol_orm.option_type or '')[0].upper() if symbol_orm and symbol_orm.option_type else ''}",
                    underlying=symbol_orm.ticker if symbol_orm else trade_orm.underlying_symbol,
                    option_type=symbol_orm.option_type.upper() if symbol_orm and symbol_orm.option_type else None,
                    strike=Decimal(str(symbol_orm.strike)) if symbol_orm and symbol_orm.strike else None,
                    expiry=symbol_orm.expiration.strftime('%Y-%m-%d') if symbol_orm and symbol_orm.expiration else None,
                    quantity=leg_orm.quantity,
                    side=leg_orm.side or 'buy',
                    entry_price=Decimal(str(leg_orm.entry_price or 0)),
                    current_price=Decimal(str(leg_orm.current_price or leg_orm.entry_price or 0)),
                    delta=Decimal(str(leg_orm.delta or 0)),
                    gamma=Decimal(str(leg_orm.gamma or 0)),
                    theta=Decimal(str(leg_orm.theta or 0)),
                    vega=Decimal(str(leg_orm.vega or 0)),
                ))

            trade = TradeState(
                trade_id=trade_orm.id,
                underlying=trade_orm.underlying_symbol,
                trade_type=trade_orm.trade_type or 'real',
                trade_status=trade_orm.trade_status or 'executed',
                strategy_type=trade_orm.strategy.strategy_type if trade_orm.strategy else 'custom',
                legs=legs,
                entry_price=Decimal(str(trade_orm.entry_price or 0)),
                current_price=Decimal(str(trade_orm.current_price or 0)),
                delta=Decimal(str(trade_orm.current_delta or 0)),
                gamma=Decimal(str(trade_orm.current_gamma or 0)),
                theta=Decimal(str(trade_orm.current_theta or 0)),
                vega=Decimal(str(trade_orm.current_vega or 0)),
                notes=trade_orm.notes or '',
                created_at=trade_orm.created_at or datetime.utcnow(),
                last_updated=trade_orm.last_updated or datetime.utcnow(),
            )

            self._trades[trade_orm.id] = trade

        self._initialized = True
        return self._detect_all_changes()

    def _detect_all_changes(self) -> Dict[str, Dict[str, Any]]:
        """Detect changes for all trades"""
        all_changes = {}

        for tid, trade in self._trades.items():
            current = trade.to_dict()
            previous = self._previous_states.get(tid, {})

            changes = {}
            for key, new_value in current.items():
                old_value = previous.get(key)
                if old_value != new_value:
                    changes[key] = {'old': old_value, 'new': new_value}

            if changes:
                all_changes[tid] = changes

        for tid in self._previous_states:
            if tid not in self._trades:
                all_changes[tid] = {'_removed': True}

        return all_changes

    def to_grid_rows(self) -> List[Dict[str, Any]]:
        """Convert all trades to AG Grid row format"""
        rows = []
        for trade in sorted(self._trades.values(), key=lambda t: t.created_at, reverse=True):
            rows.append({
                'id': trade.trade_id,
                'underlying': trade.underlying,
                'strategy': trade.strategy_type.replace('_', ' ').title(),
                'status': trade.trade_status.upper(),
                'trade_type': trade.trade_type,
                'legs': trade.legs_count,
                'delta': float(trade.delta),
                'gamma': float(trade.gamma),
                'theta': float(trade.theta),
                'vega': float(trade.vega),
                'entry_price': float(trade.entry_price),
                'current_price': float(trade.current_price),
                'pnl': float(trade.current_price - trade.entry_price) * 100,  # Assuming 100 multiplier
                'dte': trade.dte,
            })
        return rows

    def to_whatif_cards(self) -> List[Dict[str, Any]]:
        """Convert what-if trades to card format for UI"""
        cards = []
        for trade in self.get_what_if_trades():
            cards.append({
                'id': trade.trade_id,
                'underlying': trade.underlying,
                'strategy': trade.strategy_type.replace('_', ' ').title(),
                'status': trade.trade_status,
                'legs': [leg.to_dict() for leg in trade.legs],
                'delta': float(trade.delta),
                'gamma': float(trade.gamma),
                'theta': float(trade.theta),
                'vega': float(trade.vega),
                'dte': trade.dte,
            })
        return cards
