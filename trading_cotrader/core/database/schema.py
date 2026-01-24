"""
Database Schema - SQLAlchemy ORM Models

CRITICAL DESIGN DECISIONS:
1. Unique constraints to prevent duplicates
2. Indexes for query performance
3. Proper foreign keys with cascades
4. JSON columns for flexible data (market context, etc.)
5. Audit timestamps on everything
"""

from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Boolean, 
    ForeignKey, Enum as SQLEnum, JSON, Text, UniqueConstraint, Index,
    CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from decimal import Decimal

Base = declarative_base()


# ============================================================================
# Core Trading Entities
# ============================================================================

class SymbolORM(Base):
    """Symbols - cached to avoid duplicates"""
    __tablename__ = 'symbols'
    
    __table_args__ = (
        # Unique constraint: same ticker + asset_type + option details
        UniqueConstraint(
            'ticker', 'asset_type', 'option_type', 'strike', 'expiration',
            name='uix_symbol_unique'
        ),
        Index('idx_ticker', 'ticker'),
        Index('idx_expiration', 'expiration'),
    )
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(50), nullable=False)
    asset_type = Column(String(20), nullable=False)  # equity, option, future
    
    # Option-specific
    option_type = Column(String(10))  # call, put
    strike = Column(Numeric(10, 2))
    expiration = Column(DateTime)
    
    # Metadata
    description = Column(String(255))
    multiplier = Column(Integer, default=1)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PortfolioORM(Base):
    """Portfolio - top level container"""
    __tablename__ = 'portfolios'
    
    __table_args__ = (
        # One portfolio per broker account
        UniqueConstraint('broker', 'account_id', name='uix_broker_account'),
        Index('idx_broker', 'broker'),
    )
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    broker = Column(String(50), nullable=False)
    account_id = Column(String(100), nullable=False)
    
    # Cash
    cash_balance = Column(Numeric(15, 2), default=0, nullable=False)
    buying_power = Column(Numeric(15, 2), default=0, nullable=False)
    
    # Portfolio Greeks (aggregated)
    portfolio_delta = Column(Numeric(10, 4), default=0)
    portfolio_gamma = Column(Numeric(10, 6), default=0)
    portfolio_theta = Column(Numeric(10, 4), default=0)
    portfolio_vega = Column(Numeric(10, 4), default=0)
    portfolio_rho = Column(Numeric(10, 4), default=0)
    
    # Performance
    total_equity = Column(Numeric(15, 2), default=0)
    total_pnl = Column(Numeric(15, 2), default=0)
    daily_pnl = Column(Numeric(15, 2), default=0)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    positions = relationship("PositionORM", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("TradeORM", back_populates="portfolio", cascade="all, delete-orphan")
    orders = relationship("OrderORM", back_populates="portfolio", cascade="all, delete-orphan")


class PositionORM(Base):
    """Current positions - what you currently hold"""
    __tablename__ = 'positions'
    
    __table_args__ = (
        # CRITICAL: Prevent duplicate positions
        # One position per portfolio + broker_position_id
        UniqueConstraint('portfolio_id', 'broker_position_id', name='uix_portfolio_broker_position'),
        Index('idx_portfolio_positions', 'portfolio_id'),
        Index('idx_symbol', 'symbol_id'),
    )
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    symbol_id = Column(String(36), ForeignKey('symbols.id'), nullable=False)
    
    # Position details
    quantity = Column(Integer, nullable=False)  # Signed: + = long, - = short
    
    # Cost basis
    average_price = Column(Numeric(10, 4), nullable=False)
    total_cost = Column(Numeric(15, 2), nullable=False)
    
    # Current state
    current_price = Column(Numeric(10, 4))
    market_value = Column(Numeric(15, 2), default=0)
    
    # Greeks (position-level, already multiplied by quantity)
    delta = Column(Numeric(10, 4), default=0)
    gamma = Column(Numeric(10, 6), default=0)
    theta = Column(Numeric(10, 4), default=0)
    vega = Column(Numeric(10, 4), default=0)
    rho = Column(Numeric(10, 4), default=0)
    
    # Greeks timestamp
    greeks_updated_at = Column(DateTime)
    
    # Broker mapping
    broker_position_id = Column(String(100))
    
    # Associated trades (JSON array of trade IDs)
    trade_ids = Column(JSON)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    portfolio = relationship("PortfolioORM", back_populates="positions")
    symbol = relationship("SymbolORM")


class TradeORM(Base):
    """Trades - logical grouping of legs"""
    __tablename__ = 'trades'
    
    __table_args__ = (
        Index('idx_portfolio_trades', 'portfolio_id'),
        Index('idx_trades_underlying', 'underlying_symbol'),  # Changed from idx_underlying
        Index('idx_is_open', 'is_open'),
        Index('idx_opened_at', 'opened_at'),
    )
    
    trade_type = Column(String(20), nullable=False, default='real', index=True)
    # Values: 'real', 'paper', 'backtest', 'research', 'replay'
    
    trade_status = Column(String(20), nullable=False, default='intent', index=True)
    # Values: 'intent', 'pending', 'executed', 'closed', 'rejected', 'cancelled', 'abandoned'
    
    # Link intent to execution
    intent_trade_id = Column(String(36), ForeignKey('trades.id'))
    executed_trade_id = Column(String(36))
    
    # Timestamps for lifecycle
    intent_at = Column(DateTime)
    submitted_at = Column(DateTime)
    
    # Execution reality
    actual_entry = Column(Numeric(10, 4))
    actual_exit = Column(Numeric(10, 4))
    slippage = Column(Numeric(10, 4))
    max_risk = Column(Numeric(10, 2))
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    strategy_id = Column(String(36), ForeignKey('strategies.id'))
    
    # Trade metadata
    underlying_symbol = Column(String(50), nullable=False)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)
    
    # Risk management
    planned_entry = Column(Numeric(10, 4))
    planned_exit = Column(Numeric(10, 4))
    stop_loss = Column(Numeric(10, 4))
    profit_target = Column(Numeric(10, 4))
    
    # State
    is_open = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)
    tags = Column(JSON)  # Array of strings
    
    # Broker mapping
    broker_trade_id = Column(String(100))
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    portfolio = relationship("PortfolioORM", back_populates="trades")
    strategy = relationship("StrategyORM")
    legs = relationship("LegORM", back_populates="trade", cascade="all, delete-orphan")


class LegORM(Base):
    """Individual legs of a trade"""
    __tablename__ = 'legs'
    
    __table_args__ = (
        Index('idx_trade_legs', 'trade_id'),
        Index('idx_order_legs', 'order_id'),
    )
    
    id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), ForeignKey('trades.id', ondelete='CASCADE'))
    order_id = Column(String(36), ForeignKey('orders.id', ondelete='SET NULL'))
    symbol_id = Column(String(36), ForeignKey('symbols.id'), nullable=False)
    
    # Leg details
    quantity = Column(Integer, nullable=False)  # Signed
    side = Column(String(20), nullable=False)  # buy_to_open, sell_to_close, etc.
    
    # Execution
    entry_price = Column(Numeric(10, 4))
    entry_time = Column(DateTime)
    exit_price = Column(Numeric(10, 4))
    exit_time = Column(DateTime)
    
    # Current state
    current_price = Column(Numeric(10, 4))
    
    # Greeks at leg level (position-adjusted)
    delta = Column(Numeric(10, 4), default=0)
    gamma = Column(Numeric(10, 6), default=0)
    theta = Column(Numeric(10, 4), default=0)
    vega = Column(Numeric(10, 4), default=0)
    
    # Costs
    fees = Column(Numeric(10, 2), default=0)
    commission = Column(Numeric(10, 2), default=0)
    
    # Broker mapping
    broker_leg_id = Column(String(100))
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    trade = relationship("TradeORM", back_populates="legs")
    order = relationship("OrderORM", back_populates="legs")
    symbol = relationship("SymbolORM")


class StrategyORM(Base):
    """Strategy definitions"""
    __tablename__ = 'strategies'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    
    # Risk parameters
    max_profit = Column(Numeric(10, 2))
    max_loss = Column(Numeric(10, 2))
    breakeven_points = Column(JSON)  # Array of decimals
    
    # Target Greeks
    target_delta = Column(Numeric(10, 4))
    max_gamma = Column(Numeric(10, 6))
    
    description = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OrderORM(Base):
    """Orders submitted to broker"""
    __tablename__ = 'orders'
    
    __table_args__ = (
        Index('idx_portfolio_orders', 'portfolio_id'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    trade_id = Column(String(36), ForeignKey('trades.id', ondelete='SET NULL'))
    
    # Order details
    order_type = Column(String(20), nullable=False)  # market, limit, stop
    limit_price = Column(Numeric(10, 4))
    stop_price = Column(Numeric(10, 4))
    
    # State
    status = Column(String(20), nullable=False)  # pending, open, filled, cancelled
    created_at = Column(DateTime, nullable=False)
    filled_at = Column(DateTime)
    
    # Execution
    filled_quantity = Column(Integer, default=0)
    average_fill_price = Column(Numeric(10, 4))
    
    # Risk
    time_in_force = Column(String(10), default='DAY')
    
    # Broker mapping
    broker_order_id = Column(String(100))
    
    # Relationships
    portfolio = relationship("PortfolioORM", back_populates="orders")
    legs = relationship("LegORM", back_populates="order", cascade="all, delete-orphan")


# ============================================================================
# Event Sourcing for AI Learning
# ============================================================================

class TradeEventORM(Base):
    """Trade events for AI learning"""
    __tablename__ = 'trade_events'
    
    __table_args__ = (
        Index('idx_trade_events_trade_id', 'trade_id'),  # Made unique
        Index('idx_trade_events_event_type', 'event_type'),  # Made unique
        Index('idx_trade_events_timestamp', 'timestamp'),  # Made unique
        Index('idx_trade_events_underlying', 'underlying_symbol'),  # Made unique - THIS WAS THE PROBLEM
    )
    
    event_id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), ForeignKey('trades.id', ondelete='CASCADE'), nullable=True)

    
    # Event metadata
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Context (stored as JSON for flexibility)
    market_context = Column(JSON, nullable=False)  # MarketContext.to_dict()
    decision_context = Column(JSON, nullable=False)  # DecisionContext.to_dict()
    
    # Trade snapshot
    strategy_type = Column(String(50))
    underlying_symbol = Column(String(50), nullable=False)
    net_credit_debit = Column(Numeric(10, 2))
    
    # Entry Greeks
    entry_delta = Column(Numeric(10, 4))
    entry_gamma = Column(Numeric(10, 6))
    entry_theta = Column(Numeric(10, 4))
    entry_vega = Column(Numeric(10, 4))
    
    # Outcome (filled in when trade closes)
    outcome = Column(JSON)  # TradeOutcomeData.to_dict()
    
    # Metadata
    tags = Column(JSON)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RecognizedPatternORM(Base):
    """Patterns the AI has learned"""
    __tablename__ = 'recognized_patterns'
    
    __table_args__ = (
        Index('idx_pattern_type', 'pattern_type'),
    )
    
    pattern_id = Column(String(36), primary_key=True)
    pattern_type = Column(String(50), nullable=False)
    
    # Pattern details
    description = Column(Text, nullable=False)
    conditions = Column(JSON, nullable=False)
    
    # Statistics
    occurrences = Column(Integer, default=0)
    success_rate = Column(Numeric(5, 2), default=0)
    avg_pnl = Column(Numeric(10, 2), default=0)
    
    # Confidence
    confidence_score = Column(Numeric(3, 2), default=0)  # 0-1
    
    # Audit
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============================================================================
# Performance Tracking
# ============================================================================

class DailyPerformanceORM(Base):
    """Daily performance snapshots"""
    __tablename__ = 'daily_performance'
    
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'date', name='uix_portfolio_date'),
        Index('idx_portfolio_performance', 'portfolio_id', 'date'),
    )
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    date = Column(DateTime, nullable=False)
    
    # Snapshot values
    total_equity = Column(Numeric(15, 2), nullable=False)
    cash_balance = Column(Numeric(15, 2), nullable=False)
    
    # P&L
    daily_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    
    # Greeks snapshot
    portfolio_delta = Column(Numeric(10, 4))
    portfolio_theta = Column(Numeric(10, 4))
    portfolio_vega = Column(Numeric(10, 4))
    
    # Metrics
    num_positions = Column(Integer, default=0)
    num_trades = Column(Integer, default=0)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GreeksHistoryORM(Base):
    """Greeks history for positions - used for P&L attribution"""
    __tablename__ = 'greeks_history'
    
    __table_args__ = (
        Index('idx_position_greeks', 'position_id', 'timestamp'),
    )
    
    id = Column(String(36), primary_key=True)
    position_id = Column(String(36), ForeignKey('positions.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Greeks snapshot
    delta = Column(Numeric(10, 4))
    gamma = Column(Numeric(10, 6))
    theta = Column(Numeric(10, 4))
    vega = Column(Numeric(10, 4))
    rho = Column(Numeric(10, 4))
    
    # Market conditions
    underlying_price = Column(Numeric(10, 4))
    implied_volatility = Column(Numeric(5, 2))
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)