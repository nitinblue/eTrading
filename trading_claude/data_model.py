# ============================================================================
# CORE DATA MODELS - Broker Agnostic
# ============================================================================

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from decimal import Decimal
import uuid

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Core Domain Models
# ---------------------------------------------------------------------------

@dataclass
class Symbol:
    """Represents a tradeable instrument"""
    ticker: str
    asset_type: AssetType
    
    # Option-specific fields
    option_type: Optional[OptionType] = None
    strike: Optional[Decimal] = None
    expiration: Optional[datetime] = None
    
    # Metadata
    description: Optional[str] = None
    multiplier: int = 1
    
    def __post_init__(self):
        if self.asset_type == AssetType.OPTION:
            assert self.option_type is not None
            assert self.strike is not None
            assert self.expiration is not None
    
    def get_option_symbol(self) -> str:
        """Generate OCC option symbol format"""
        if self.asset_type != AssetType.OPTION:
            return self.ticker
        
        exp_str = self.expiration.strftime("%y%m%d")
        opt_type = "C" if self.option_type == OptionType.CALL else "P"
        strike_str = f"{int(self.strike * 1000):08d}"
        return f"{self.ticker:<6}{exp_str}{opt_type}{strike_str}"
    
    def get_streamer_symbol(self) -> str:
        """Generate OCC option symbol format"""
        if self.asset_type != AssetType.OPTION:
            return self.ticker
        
        exp_str = self.expiration.strftime("%y%m%d")
        opt_type = "C" if self.option_type == OptionType.CALL else "P"
        strike10 = f"{int(self.strike)}"
        # Ticker uppercase, no spaces
        ticker = self.ticker.replace(" ", "").upper()    
        return f".{ticker}{exp_str}{opt_type}{strike10}"


@dataclass
class Leg:
    """Represents a single leg in a trade"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    quantity: int = 0  # Positive for long, negative for short
    side: OrderSide = None
    
    # Execution details
    entry_price: Optional[Decimal] = None
    entry_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    exit_time: Optional[datetime] = None
    
    # Current state
    current_price: Optional[Decimal] = None
    
    # Metadata
    broker_leg_id: Optional[str] = None
    fees: Decimal = Decimal('0')
    
    def is_long(self) -> bool:
        return self.quantity > 0
    
    def is_short(self) -> bool:
        return self.quantity < 0
    
    def unrealized_pnl(self) -> Decimal:
        if not self.entry_price or not self.current_price:
            return Decimal('0')
        
        pnl = (self.current_price - self.entry_price) * self.quantity * self.symbol.multiplier
        return pnl
    
    def realized_pnl(self) -> Decimal:
        if not self.entry_price or not self.exit_price:
            return Decimal('0')
        
        pnl = (self.exit_price - self.entry_price) * self.quantity * self.symbol.multiplier
        return pnl - self.fees


@dataclass
class Strategy:
    """Defines a trading strategy template"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy_type: StrategyType = StrategyType.SINGLE
    
    # Risk metrics
    max_profit: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    breakeven_points: List[Decimal] = field(default_factory=list)
    
    # Greeks aggregation
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    
    description: Optional[str] = None


@dataclass
class Trade:
    """Represents a complete trade with one or more legs"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    legs: List[Leg] = field(default_factory=list)
    strategy: Optional[Strategy] = None
    
    # Trade metadata
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    underlying_symbol: str = ""
    
    # Risk parameters
    planned_entry: Optional[Decimal] = None
    planned_exit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    
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
        if self.is_open:
            return self.total_unrealized_pnl()
        return self.total_realized_pnl()
    
    def net_cost(self) -> Decimal:
        """Calculate net debit/credit"""
        total = Decimal('0')
        for leg in self.legs:
            if leg.entry_price:
                cost = leg.entry_price * abs(leg.quantity) * leg.symbol.multiplier
                total += cost if leg.quantity > 0 else -cost
        return total


@dataclass
class Position:
    """Current position (aggregated view of open legs)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    quantity: int = 0  # Net position
    
    # Cost basis
    average_price: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    
    # Current state
    current_price: Optional[Decimal] = None
    market_value: Decimal = Decimal('0')
    
    # Associated trades
    trade_ids: List[str] = field(default_factory=list)
    
    # Greeks (for options)
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    
    # Metadata
    broker_position_id: Optional[str] = None
    
    def unrealized_pnl(self) -> Decimal:
        if not self.current_price:
            return Decimal('0')
        
        current_value = self.current_price * self.quantity * self.symbol.multiplier
        return current_value - self.total_cost


@dataclass
class Order:
    """Represents an order (can create multiple legs)"""
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
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK
    
    # Metadata
    broker_order_id: Optional[str] = None
    trade_id: Optional[str] = None
    
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    def is_open(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL]


@dataclass
class Portfolio:
    """Top-level portfolio containing all trades and positions"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    broker: str = ""
    account_id: str = ""
    
    # Holdings
    trades: Dict[str, Trade] = field(default_factory=dict)
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    
    # Cash
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    
    # Risk metrics
    portfolio_delta: Decimal = Decimal('0')
    portfolio_gamma: Decimal = Decimal('0')
    portfolio_theta: Decimal = Decimal('0')
    portfolio_vega: Decimal = Decimal('0')
    
    # Performance
    total_equity: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    
    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def get_total_market_value(self) -> Decimal:
        return sum(pos.market_value for pos in self.positions.values())
    
    def get_total_unrealized_pnl(self) -> Decimal:
        return sum(pos.unrealized_pnl() for pos in self.positions.values())
    
    def get_open_trades(self) -> List[Trade]:
        return [t for t in self.trades.values() if t.is_open]
    
    def get_closed_trades(self) -> List[Trade]:
        return [t for t in self.trades.values() if not t.is_open]


# ============================================================================
# DATABASE LAYER - SQLAlchemy ORM
# ============================================================================

from sqlalchemy import create_engine, Column, String, Integer, Numeric, DateTime, Boolean, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class SymbolORM(Base):
    __tablename__ = 'symbols'
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(50), nullable=False, index=True)
    asset_type = Column(SQLEnum(AssetType), nullable=False)
    option_type = Column(SQLEnum(OptionType))
    strike = Column(Numeric(10, 2))
    expiration = Column(DateTime)
    description = Column(String(255))
    multiplier = Column(Integer, default=1)

class LegORM(Base):
    __tablename__ = 'legs'
    
    id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), ForeignKey('trades.id'))
    order_id = Column(String(36), ForeignKey('orders.id'))
    
    symbol_id = Column(String(36), ForeignKey('symbols.id'))
    quantity = Column(Integer, nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    
    entry_price = Column(Numeric(10, 4))
    entry_time = Column(DateTime)
    exit_price = Column(Numeric(10, 4))
    exit_time = Column(DateTime)
    current_price = Column(Numeric(10, 4))
    
    broker_leg_id = Column(String(100))
    fees = Column(Numeric(10, 2), default=0)
    
    symbol = relationship("SymbolORM")

class StrategyORM(Base):
    __tablename__ = 'strategies'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    strategy_type = Column(SQLEnum(StrategyType), nullable=False)
    
    max_profit = Column(Numeric(10, 2))
    max_loss = Column(Numeric(10, 2))
    breakeven_points = Column(JSON)
    
    delta = Column(Numeric(10, 4), default=0)
    gamma = Column(Numeric(10, 4), default=0)
    theta = Column(Numeric(10, 4), default=0)
    vega = Column(Numeric(10, 4), default=0)
    
    description = Column(String(500))

class TradeORM(Base):
    __tablename__ = 'trades'
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'))
    strategy_id = Column(String(36), ForeignKey('strategies.id'))
    
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)
    underlying_symbol = Column(String(50), index=True)
    
    planned_entry = Column(Numeric(10, 4))
    planned_exit = Column(Numeric(10, 4))
    stop_loss = Column(Numeric(10, 4))
    
    is_open = Column(Boolean, default=True, index=True)
    notes = Column(String(1000))
    tags = Column(JSON)
    
    broker_trade_id = Column(String(100))
    
    legs = relationship("LegORM", foreign_keys=[LegORM.trade_id])
    strategy = relationship("StrategyORM")

class PositionORM(Base):
    __tablename__ = 'positions'
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'))
    symbol_id = Column(String(36), ForeignKey('symbols.id'))   
    quantity = Column(Integer, nullable=False)
    average_price = Column(Numeric(10, 4), nullable=False)
    total_cost = Column(Numeric(10, 2), nullable=False)
    
    current_price = Column(Numeric(10, 4))
    market_value = Column(Numeric(10, 2))
    
    trade_ids = Column(JSON)
    
    delta = Column(Numeric(10, 4), default=0)
    gamma = Column(Numeric(10, 4), default=0)
    theta = Column(Numeric(10, 4), default=0)
    vega = Column(Numeric(10, 4), default=0)
    
    broker_position_id = Column(String(100))
    
    symbol = relationship("SymbolORM")

class OrderORM(Base):
    __tablename__ = 'orders'
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id'))
    trade_id = Column(String(36), ForeignKey('trades.id'))
    
    order_type = Column(SQLEnum(OrderType), nullable=False)
    limit_price = Column(Numeric(10, 4))
    stop_price = Column(Numeric(10, 4))
    
    status = Column(SQLEnum(OrderStatus), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)
    filled_at = Column(DateTime)
    
    filled_quantity = Column(Integer, default=0)
    average_fill_price = Column(Numeric(10, 4))
    
    time_in_force = Column(String(10), default="DAY")
    broker_order_id = Column(String(100))
    
    legs = relationship("LegORM", foreign_keys=[LegORM.order_id])

class PortfolioORM(Base):
    __tablename__ = 'portfolios'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    account_id = Column(String(100), nullable=False)
    
    cash_balance = Column(Numeric(15, 2), default=0)
    buying_power = Column(Numeric(15, 2), default=0)
    
    portfolio_delta = Column(Numeric(10, 4), default=0)
    portfolio_gamma = Column(Numeric(10, 4), default=0)
    portfolio_theta = Column(Numeric(10, 4), default=0)
    portfolio_vega = Column(Numeric(10, 4), default=0)
    
    total_equity = Column(Numeric(15, 2), default=0)
    total_pnl = Column(Numeric(15, 2), default=0)
    
    last_updated = Column(DateTime, nullable=False)
    
    trades = relationship("TradeORM", back_populates="portfolio")
    positions = relationship("PositionORM")
    orders = relationship("OrderORM")

TradeORM.portfolio = relationship("PortfolioORM", back_populates="trades")


# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_database(db_url: str = "sqlite:///portfolio.db"):
    """Initialize database and create tables"""
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    """Get database session"""
    Session = sessionmaker(bind=engine)
    return Session()


# Example usage:
if __name__ == "__main__":
    # Initialize database
    engine = init_database()
    session = get_session(engine)
    
    print("Database initialized successfully!")
    print("Tables created:", Base.metadata.tables.keys())