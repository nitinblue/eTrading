"""
Core Domain Models - Pure business logic, no dependencies

These models represent your trading domain concepts.
Immutable where possible, rich with business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
from decimal import Decimal
import uuid


# ============================================================================
# Enumerations
# ============================================================================

class AssetType(Enum):
    EQUITY = "equity"
    OPTION = "option"
    FUTURE = "future"
    CRYPTO = "crypto"


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_CLOSE = "sell_to_close"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class StrategyType(Enum):
    SINGLE = "single"
    VERTICAL_SPREAD = "vertical_spread"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    COVERED_CALL = "covered_call"
    PROTECTIVE_PUT = "protective_put"
    CUSTOM = "custom"


# ============================================================================
# Value Objects
# ============================================================================

@dataclass(frozen=True)
class Symbol:
    """Immutable symbol representation"""
    ticker: str
    asset_type: AssetType
    
    # Option-specific (None for non-options)
    option_type: Optional[OptionType] = None
    strike: Optional[Decimal] = None
    expiration: Optional[datetime] = None
    
    # Metadata
    description: Optional[str] = None
    multiplier: int = 1
    
    def __post_init__(self):
        if self.asset_type == AssetType.OPTION:
            if not all([self.option_type, self.strike, self.expiration]):
                raise ValueError("Options must have option_type, strike, and expiration")
    
    def get_option_symbol(self) -> str:
        """Generate OCC option symbol format"""
        if self.asset_type != AssetType.OPTION:
            return self.ticker
        
        exp_str = self.expiration.strftime("%y%m%d")
        opt_type = "C" if self.option_type == OptionType.CALL else "P"
        strike_str = f"{int(self.strike * 1000):08d}"
        return f"{self.ticker:<6}{exp_str}{opt_type}{strike_str}"
    
    def is_itm(self, underlying_price: Decimal) -> bool:
        """Check if option is in-the-money"""
        if self.asset_type != AssetType.OPTION:
            return False
        
        if self.option_type == OptionType.CALL:
            return underlying_price > self.strike
        else:
            return underlying_price < self.strike
    
    def days_to_expiration(self) -> int:
        """Days until expiration"""
        if not self.expiration:
            return 0
        return (self.expiration - datetime.utcnow()).days


@dataclass(frozen=True)
class Greeks:
    """Option Greeks - immutable snapshot"""
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    rho: Decimal = Decimal('0')
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def total_risk(self) -> Decimal:
        """Simple risk score based on Greeks"""
        return abs(self.delta) + abs(self.gamma * 100) + abs(self.theta)


# ============================================================================
# Entities
# ============================================================================

@dataclass
class Leg:
    """
    A single leg in a trade
    Can be long or short (indicated by quantity sign)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    quantity: int = 0  # Positive = long, Negative = short
    side: OrderSide = None
    
    # Execution details
    entry_price: Optional[Decimal] = None
    entry_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    exit_time: Optional[datetime] = None
    
    # Current state
    current_price: Optional[Decimal] = None
    greeks: Optional[Greeks] = None
    
    # Metadata
    broker_leg_id: Optional[str] = None
    fees: Decimal = Decimal('0')
    commission: Decimal = Decimal('0')
    
    def is_long(self) -> bool:
        return self.quantity > 0
    
    def is_short(self) -> bool:
        return self.quantity < 0
    
    def is_open(self) -> bool:
        return self.exit_time is None
    
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L"""
        if not self.entry_price or not self.current_price:
            return Decimal('0')
        
        pnl = (self.current_price - self.entry_price) * self.quantity * self.symbol.multiplier
        return pnl - self.fees - self.commission
    
    def realized_pnl(self) -> Decimal:
        """Calculate realized P&L"""
        if not self.entry_price or not self.exit_price:
            return Decimal('0')
        
        pnl = (self.exit_price - self.entry_price) * self.quantity * self.symbol.multiplier
        return pnl - self.fees - self.commission
    
    def total_pnl(self) -> Decimal:
        """Total P&L (realized if closed, unrealized if open)"""
        return self.realized_pnl() if not self.is_open() else self.unrealized_pnl()


@dataclass
class Strategy:
    """Trading strategy definition"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy_type: StrategyType = StrategyType.SINGLE
    
    # Risk metrics
    max_profit: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    breakeven_points: List[Decimal] = field(default_factory=list)
    
    # Greeks aggregation
    target_delta: Optional[Decimal] = None
    max_gamma: Optional[Decimal] = None
    
    description: Optional[str] = None
    
    def probability_of_profit(self, current_price: Decimal, iv: Decimal) -> float:
        """
        Calculate probability of profit (simplified)
        In production, use proper options pricing model
        """
        # Placeholder - implement with Black-Scholes
        return 0.5


@dataclass
class Trade:
    """
    A trade consists of one or more legs
    Represents a complete trading position/strategy
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    legs: List[Leg] = field(default_factory=list)
    strategy: Optional[Strategy] = None
    
    # Trade metadata
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    underlying_symbol: str = ""
    
    # Risk management
    planned_entry: Optional[Decimal] = None
    planned_exit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    profit_target: Optional[Decimal] = None
    
    # State
    is_open: bool = True
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Broker mapping
    broker_trade_id: Optional[str] = None
    
    def total_unrealized_pnl(self) -> Decimal:
        return sum(leg.unrealized_pnl() for leg in self.legs)
    
    def total_realized_pnl(self) -> Decimal:
        return sum(leg.realized_pnl() for leg in self.legs)
    
    def total_pnl(self) -> Decimal:
        return self.total_unrealized_pnl() if self.is_open else self.total_realized_pnl()
    
    def net_cost(self) -> Decimal:
        """Calculate net debit/credit"""
        total = Decimal('0')
        for leg in self.legs:
            if leg.entry_price:
                cost = leg.entry_price * abs(leg.quantity) * leg.symbol.multiplier
                total += cost if leg.quantity > 0 else -cost
        return total
    
    def total_greeks(self) -> Greeks:
        """Aggregate Greeks across all legs"""
        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')
        
        for leg in self.legs:
            if leg.greeks:
                # Greeks are already position-adjusted in the leg
                total_delta += leg.greeks.delta
                total_gamma += leg.greeks.gamma
                total_theta += leg.greeks.theta
                total_vega += leg.greeks.vega
        
        return Greeks(
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega
        )
    
    def days_to_expiration(self) -> Optional[int]:
        """Days to nearest expiration"""
        dte_list = []
        for leg in self.legs:
            if leg.symbol.expiration:
                dte = leg.symbol.days_to_expiration()
                dte_list.append(dte)
        
        return min(dte_list) if dte_list else None
    
    def return_on_capital(self) -> Optional[Decimal]:
        """Calculate ROC"""
        net_cost = abs(self.net_cost())
        if net_cost == 0:
            return None
        
        return (self.total_pnl() / net_cost) * 100


@dataclass
class Position:
    """
    Current position snapshot (aggregated view)
    Represents what you currently hold
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    quantity: int = 0  # Signed: positive = long, negative = short
    
    # Cost basis
    average_price: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    
    # Current state
    current_price: Optional[Decimal] = None
    market_value: Decimal = Decimal('0')
    greeks: Optional[Greeks] = None
    
    # Associated trades
    trade_ids: List[str] = field(default_factory=list)
    
    # Metadata
    broker_position_id: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def is_long(self) -> bool:
        return self.quantity > 0
    
    def is_short(self) -> bool:
        return self.quantity < 0
    
    def unrealized_pnl(self) -> Decimal:
        if not self.current_price:
            return Decimal('0')
        
        current_value = self.current_price * self.quantity * self.symbol.multiplier
        return current_value - self.total_cost
    
    def pnl_percent(self) -> Decimal:
        if self.total_cost == 0:
            return Decimal('0')
        return (self.unrealized_pnl() / abs(self.total_cost)) * 100


@dataclass
class Order:
    """Order to be submitted to broker"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    legs: List[Leg] = field(default_factory=list)
    
    # Order details
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    
    # State
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    
    # Execution
    filled_quantity: int = 0
    average_fill_price: Optional[Decimal] = None
    
    # Risk
    time_in_force: str = "DAY"
    
    # Metadata
    broker_order_id: Optional[str] = None
    trade_id: Optional[str] = None
    
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    def is_open(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL]


@dataclass
class Portfolio:
    """Top-level portfolio container"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    broker: str = ""
    account_id: str = ""
    
    # Cash
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    
    # Risk metrics
    portfolio_greeks: Optional[Greeks] = None
    
    # Performance
    total_equity: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    daily_pnl: Decimal = Decimal('0')
    
    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def net_liquidating_value(self) -> Decimal:
        """Total account value"""
        return self.total_equity + self.cash_balance