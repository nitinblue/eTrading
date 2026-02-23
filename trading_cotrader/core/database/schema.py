"""
Enhanced Database Schema - SQLAlchemy ORM Models

NEW ADDITIONS:
1. PortfolioORM.portfolio_type - Support for what-if portfolios
2. PortfolioORM risk limits - Per-portfolio configurable limits
3. PositionPnLSnapshotORM - P&L attribution by Greek
4. PositionGreeksSnapshotORM - Opening vs current Greeks
5. TradeORM enhanced - Entry/exit Greeks, underlying price, IV
6. WhatIfPortfolioConfigORM - Configuration for what-if portfolios

CRITICAL DESIGN DECISIONS:
1. Opening state captured at execution (immutable)
2. Current state updated with market (mutable)
3. P&L attribution calculated from opening vs current
4. What-if portfolios have configurable capital and limits
"""

from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Boolean, 
    ForeignKey, Enum as SQLEnum, JSON, Text, UniqueConstraint, Index,
    CheckConstraint, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from decimal import Decimal

Base = declarative_base()


# ============================================================================
# Core Trading Entities (Enhanced)
# ============================================================================

class SymbolORM(Base):
    """Symbols - cached to avoid duplicates"""
    __tablename__ = 'symbols'
    
    __table_args__ = (
        UniqueConstraint(
            'ticker', 'asset_type', 'option_type', 'strike', 'expiration',
            name='uix_symbol_unique'
        ),
        Index('idx_ticker', 'ticker'),
        Index('idx_expiration', 'expiration'),
    )
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(50), nullable=False)
    asset_type = Column(String(20), nullable=False)  # equity, option, future, index
    
    # Option-specific
    option_type = Column(String(10))  # call, put
    strike = Column(Numeric(10, 2))
    expiration = Column(DateTime)
    
    # Metadata
    description = Column(String(255))
    multiplier = Column(Integer, default=100)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PortfolioORM(Base):
    """
    Portfolio - top level container
    
    ENHANCED: Supports real and what-if portfolios with configurable limits
    """
    __tablename__ = 'portfolios'
    
    __table_args__ = (
        UniqueConstraint('broker', 'account_id', name='uix_broker_account'),
        Index('idx_broker', 'broker'),
        Index('idx_portfolio_type', 'portfolio_type'),
    )
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    
    # === TYPE ===
    portfolio_type = Column(String(20), nullable=False, default='real')
    # Values: 'real', 'paper', 'what_if', 'backtest'
    
    # === BROKER (null for what-if) ===
    broker = Column(String(50))
    account_id = Column(String(100))
    
    # === CAPITAL ===
    initial_capital = Column(Numeric(15, 2), default=0)  # Starting capital (for what-if)
    cash_balance = Column(Numeric(15, 2), default=0, nullable=False)
    buying_power = Column(Numeric(15, 2), default=0, nullable=False)
    total_equity = Column(Numeric(15, 2), default=0)
    
    # === PORTFOLIO GREEKS ===
    portfolio_delta = Column(Numeric(10, 4), default=0)
    portfolio_gamma = Column(Numeric(10, 6), default=0)
    portfolio_theta = Column(Numeric(10, 4), default=0)
    portfolio_vega = Column(Numeric(10, 4), default=0)
    portfolio_rho = Column(Numeric(10, 4), default=0)
    
    # === RISK LIMITS (per portfolio) ===
    max_portfolio_delta = Column(Numeric(10, 2), default=500)
    max_portfolio_gamma = Column(Numeric(10, 4), default=50)
    min_portfolio_theta = Column(Numeric(10, 2), default=-500)
    max_portfolio_vega = Column(Numeric(10, 2), default=1000)
    max_position_size_pct = Column(Numeric(5, 2), default=10)
    max_single_trade_risk_pct = Column(Numeric(5, 2), default=5)
    max_total_risk_pct = Column(Numeric(5, 2), default=25)
    min_cash_reserve_pct = Column(Numeric(5, 2), default=10)
    max_concentration_pct = Column(Numeric(5, 2), default=25)
    
    # === RISK METRICS (computed) ===
    var_1d_95 = Column(Numeric(15, 2), default=0)
    var_1d_99 = Column(Numeric(15, 2), default=0)
    beta = Column(Numeric(5, 4), default=1)
    
    # === PERFORMANCE ===
    total_pnl = Column(Numeric(15, 2), default=0)
    daily_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    
    # === METADATA ===
    description = Column(Text)
    tags = Column(JSON)  # Array of strings
    
    # === AUDIT ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    positions = relationship("PositionORM", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("TradeORM", back_populates="portfolio", cascade="all, delete-orphan")
    orders = relationship("OrderORM", back_populates="portfolio", cascade="all, delete-orphan")
    daily_snapshots = relationship("DailyPerformanceORM", back_populates="portfolio", cascade="all, delete-orphan")


class PositionORM(Base):
    """
    Current positions - what you currently hold
    
    ENHANCED: Tracks opening state for P&L attribution
    """
    __tablename__ = 'positions'
    
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'broker_position_id', name='uix_portfolio_broker_position'),
        Index('idx_portfolio_positions', 'portfolio_id'),
        Index('idx_symbol', 'symbol_id'),
    )
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    symbol_id = Column(String(36), ForeignKey('symbols.id'), nullable=False)
    
    # === POSITION DETAILS ===
    quantity = Column(Integer, nullable=False)  # Signed: + = long, - = short
    
    # === OPENING STATE (immutable after fill) ===
    entry_price = Column(Numeric(10, 4), nullable=False)
    entry_time = Column(DateTime)
    entry_underlying_price = Column(Numeric(10, 4))
    entry_iv = Column(Numeric(5, 4))  # e.g., 0.25 for 25%
    total_cost = Column(Numeric(15, 2), nullable=False)
    
    # Opening Greeks
    entry_delta = Column(Numeric(10, 4), default=0)
    entry_gamma = Column(Numeric(10, 6), default=0)
    entry_theta = Column(Numeric(10, 4), default=0)
    entry_vega = Column(Numeric(10, 4), default=0)
    entry_rho = Column(Numeric(10, 4), default=0)
    
    # === CURRENT STATE (updates with market) ===
    current_price = Column(Numeric(10, 4))
    current_underlying_price = Column(Numeric(10, 4))
    current_iv = Column(Numeric(5, 4))
    market_value = Column(Numeric(15, 2), default=0)
    
    # Current Greeks (position-level, already multiplied by quantity)
    delta = Column(Numeric(10, 4), default=0)
    gamma = Column(Numeric(10, 6), default=0)
    theta = Column(Numeric(10, 4), default=0)
    vega = Column(Numeric(10, 4), default=0)
    rho = Column(Numeric(10, 4), default=0)
    
    greeks_updated_at = Column(DateTime)
    
    # === P&L ATTRIBUTION (computed) ===
    delta_pnl = Column(Numeric(15, 2), default=0)
    gamma_pnl = Column(Numeric(15, 2), default=0)
    theta_pnl = Column(Numeric(15, 2), default=0)
    vega_pnl = Column(Numeric(15, 2), default=0)
    unexplained_pnl = Column(Numeric(15, 2), default=0)
    total_pnl = Column(Numeric(15, 2), default=0)
    
    # === BROKER MAPPING ===
    broker_position_id = Column(String(100))
    trade_ids = Column(JSON)  # Array of trade IDs
    
    # === AUDIT ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    portfolio = relationship("PortfolioORM", back_populates="positions")
    symbol = relationship("SymbolORM")
    greeks_history = relationship("PositionGreeksSnapshotORM", back_populates="position", cascade="all, delete-orphan")
    pnl_history = relationship("PositionPnLSnapshotORM", back_populates="position", cascade="all, delete-orphan")


class PositionGreeksSnapshotORM(Base):
    """
    Greeks snapshots for a position over time.
    
    Used for:
    - P&L attribution calculation
    - Greeks evolution analysis
    - Risk monitoring
    """
    __tablename__ = 'position_greeks_snapshots'
    
    __table_args__ = (
        Index('idx_position_greeks_time', 'position_id', 'timestamp'),
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
    
    # Market conditions at snapshot
    underlying_price = Column(Numeric(10, 4))
    option_price = Column(Numeric(10, 4))
    implied_volatility = Column(Numeric(5, 4))
    
    # Relationships
    position = relationship("PositionORM", back_populates="greeks_history")


class PositionPnLSnapshotORM(Base):
    """
    P&L attribution snapshots for a position.
    
    Explains P&L by Greek component.
    """
    __tablename__ = 'position_pnl_snapshots'
    
    __table_args__ = (
        Index('idx_position_pnl_time', 'position_id', 'timestamp'),
        Index('idx_position_pnl_date', 'position_id', 'snapshot_date'),
    )
    
    id = Column(String(36), primary_key=True)
    position_id = Column(String(36), ForeignKey('positions.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    snapshot_date = Column(Date, nullable=False)
    
    # P&L attribution
    delta_pnl = Column(Numeric(15, 2), default=0)
    gamma_pnl = Column(Numeric(15, 2), default=0)
    theta_pnl = Column(Numeric(15, 2), default=0)
    vega_pnl = Column(Numeric(15, 2), default=0)
    rho_pnl = Column(Numeric(15, 2), default=0)
    unexplained_pnl = Column(Numeric(15, 2), default=0)
    
    # Totals
    model_pnl = Column(Numeric(15, 2), default=0)  # Sum of Greek P&Ls
    actual_pnl = Column(Numeric(15, 2), default=0)  # From broker
    attribution_error = Column(Numeric(15, 2), default=0)  # actual - model
    
    # Market changes
    underlying_change = Column(Numeric(10, 4), default=0)
    iv_change = Column(Numeric(5, 4), default=0)
    time_passed_days = Column(Numeric(5, 2), default=0)
    
    # Relationships
    position = relationship("PositionORM", back_populates="pnl_history")


class TradeORM(Base):
    """
    Trades - logical grouping of legs
    
    ENHANCED: 
    - Entry/exit state for P&L attribution
    - What-if trade support
    - Trade lifecycle tracking
    """
    __tablename__ = 'trades'
    
    __table_args__ = (
        Index('idx_portfolio_trades', 'portfolio_id'),
        Index('idx_trades_underlying', 'underlying_symbol'),
        Index('idx_is_open', 'is_open'),
        Index('idx_trade_type', 'trade_type'),
        Index('idx_trade_status', 'trade_status'),
        Index('idx_opened_at', 'opened_at'),
    )
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    strategy_id = Column(String(36), ForeignKey('strategies.id'))
    
    # === CLASSIFICATION ===
    trade_type = Column(String(20), nullable=False, default='real')
    # Values: 'real', 'paper', 'what_if', 'backtest', 'research', 'replay'
    
    trade_status = Column(String(20), nullable=False, default='intent')
    # Values: 'intent', 'evaluated', 'pending', 'partial', 'executed', 'closed', 'rolled', 'rejected', 'cancelled', 'abandoned', 'expired'
    
    # === TRADE METADATA ===
    underlying_symbol = Column(String(50), nullable=False)
    
    # === TIMESTAMPS ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    intent_at = Column(DateTime)
    evaluated_at = Column(DateTime)
    submitted_at = Column(DateTime)
    opened_at = Column(DateTime)
    executed_at = Column(DateTime)
    closed_at = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # === OPENING STATE (immutable after fill) ===
    entry_price = Column(Numeric(10, 4))  # Net debit/credit
    entry_underlying_price = Column(Numeric(10, 4))
    entry_iv = Column(Numeric(5, 4))
    
    # Entry Greeks (trade-level)
    entry_delta = Column(Numeric(10, 4), default=0)
    entry_gamma = Column(Numeric(10, 6), default=0)
    entry_theta = Column(Numeric(10, 4), default=0)
    entry_vega = Column(Numeric(10, 4), default=0)
    
    # === CURRENT STATE ===
    current_price = Column(Numeric(10, 4))
    current_underlying_price = Column(Numeric(10, 4))
    current_iv = Column(Numeric(5, 4))
    
    # Current Greeks
    current_delta = Column(Numeric(10, 4), default=0)
    current_gamma = Column(Numeric(10, 6), default=0)
    current_theta = Column(Numeric(10, 4), default=0)
    current_vega = Column(Numeric(10, 4), default=0)
    
    # === EXIT STATE ===
    exit_price = Column(Numeric(10, 4))
    exit_underlying_price = Column(Numeric(10, 4))
    exit_reason = Column(String(100))
    
    # === P&L ATTRIBUTION ===
    delta_pnl = Column(Numeric(15, 2), default=0)
    gamma_pnl = Column(Numeric(15, 2), default=0)
    theta_pnl = Column(Numeric(15, 2), default=0)
    vega_pnl = Column(Numeric(15, 2), default=0)
    unexplained_pnl = Column(Numeric(15, 2), default=0)
    total_pnl = Column(Numeric(15, 2), default=0)
    
    # === RISK MANAGEMENT ===
    planned_entry = Column(Numeric(10, 4))
    actual_entry = Column(Numeric(10, 4))
    actual_exit = Column(Numeric(10, 4))
    slippage = Column(Numeric(10, 4))
    max_risk = Column(Numeric(10, 2))
    stop_loss = Column(Numeric(10, 4))
    profit_target = Column(Numeric(10, 4))
    
    # === LINKAGE ===
    intent_trade_id = Column(String(36), ForeignKey('trades.id'))
    executed_trade_id = Column(String(36))
    rolled_from_id = Column(String(36))
    rolled_to_id = Column(String(36))
    
    # === SOURCE TRACKING ===
    trade_source = Column(String(50), default='manual')
    # Values: 'manual', 'screener_vix', 'screener_iv_rank', 'screener_technical',
    #         'astrology', 'ai_recommendation', 'research', 'hedge'
    recommendation_id = Column(String(36))  # FK to recommendations table

    # === STATE ===
    is_open = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)
    tags = Column(JSON)
    
    # === BROKER MAPPING ===
    broker_trade_id = Column(String(100))
    
    # Relationships
    portfolio = relationship("PortfolioORM", back_populates="trades")
    strategy = relationship("StrategyORM")
    legs = relationship("LegORM", back_populates="trade", cascade="all, delete-orphan")
    events = relationship("TradeEventORM", back_populates="trade", cascade="all, delete-orphan")


class LegORM(Base):
    """
    Individual legs of a trade
    
    ENHANCED: Opening vs current state for P&L attribution
    """
    __tablename__ = 'legs'
    
    __table_args__ = (
        Index('idx_trade_legs', 'trade_id'),
        Index('idx_order_legs', 'order_id'),
    )
    
    id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), ForeignKey('trades.id', ondelete='CASCADE'))
    order_id = Column(String(36), ForeignKey('orders.id', ondelete='SET NULL'))
    symbol_id = Column(String(36), ForeignKey('symbols.id'), nullable=False)
    
    # === LEG DETAILS ===
    quantity = Column(Integer, nullable=False)  # Signed
    side = Column(String(20), nullable=False)   # buy, sell, buy_to_open, etc.
    
    # === OPENING STATE ===
    entry_price = Column(Numeric(10, 4))
    entry_time = Column(DateTime)
    entry_underlying_price = Column(Numeric(10, 4))
    entry_iv = Column(Numeric(5, 4))
    
    # Entry Greeks (per contract, not position-adjusted)
    entry_delta = Column(Numeric(10, 4), default=0)
    entry_gamma = Column(Numeric(10, 6), default=0)
    entry_theta = Column(Numeric(10, 4), default=0)
    entry_vega = Column(Numeric(10, 4), default=0)
    
    # === CURRENT STATE ===
    current_price = Column(Numeric(10, 4))
    current_underlying_price = Column(Numeric(10, 4))
    current_iv = Column(Numeric(5, 4))
    
    # Current Greeks
    delta = Column(Numeric(10, 4), default=0)
    gamma = Column(Numeric(10, 6), default=0)
    theta = Column(Numeric(10, 4), default=0)
    vega = Column(Numeric(10, 4), default=0)
    
    # === EXIT STATE ===
    exit_price = Column(Numeric(10, 4))
    exit_time = Column(DateTime)
    
    # === COSTS ===
    fees = Column(Numeric(10, 2), default=0)
    commission = Column(Numeric(10, 2), default=0)
    
    # === BROKER MAPPING ===
    broker_leg_id = Column(String(100))
    
    # === AUDIT ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    trade = relationship("TradeORM", back_populates="legs")
    order = relationship("OrderORM", back_populates="legs")
    symbol = relationship("SymbolORM")


class StrategyORM(Base):
    """Strategy definitions with exit rules"""
    __tablename__ = 'strategies'
    
    __table_args__ = (
        Index('idx_strategy_type', 'strategy_type'),
    )
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    
    # === RISK CLASSIFICATION ===
    risk_category = Column(String(20), default='defined')  # defined, undefined, mixed
    
    # === RISK PARAMETERS ===
    max_profit = Column(Numeric(10, 2))
    max_loss = Column(Numeric(10, 2))
    breakeven_points = Column(JSON)  # Array of decimals
    
    # === PROBABILITY METRICS ===
    probability_of_profit = Column(Numeric(5, 4))
    expected_value = Column(Numeric(10, 2))
    
    # === TARGET GREEKS ===
    target_delta = Column(Numeric(10, 4))
    max_gamma = Column(Numeric(10, 6))
    target_theta = Column(Numeric(10, 4))
    
    # === EXIT RULES ===
    profit_target_pct = Column(Numeric(5, 2), default=50)  # Close at 50% profit
    stop_loss_pct = Column(Numeric(5, 2), default=200)     # Close at 200% loss
    dte_exit = Column(Integer, default=7)                   # Close at 7 DTE
    
    description = Column(Text)
    
    # === AUDIT ===
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
        Index('idx_trade_events_trade_id', 'trade_id'),
        Index('idx_trade_events_event_type', 'event_type'),
        Index('idx_trade_events_timestamp', 'timestamp'),
        Index('idx_trade_events_underlying', 'underlying_symbol'),
    )
    
    event_id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), ForeignKey('trades.id', ondelete='CASCADE'), nullable=True)
    
    # Event metadata
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Context (stored as JSON for flexibility)
    market_context = Column(JSON, nullable=False)
    decision_context = Column(JSON, nullable=False)
    
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
    outcome = Column(JSON)
    
    # Metadata
    tags = Column(JSON)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    trade = relationship("TradeORM", back_populates="events")


class RecognizedPatternORM(Base):
    """Patterns the AI has learned"""
    __tablename__ = 'recognized_patterns'
    
    __table_args__ = (
        Index('idx_pattern_type', 'pattern_type'),
    )
    
    pattern_id = Column(String(36), primary_key=True)
    pattern_type = Column(String(50), nullable=False)
    
    description = Column(Text, nullable=False)
    conditions = Column(JSON, nullable=False)
    
    # Statistics
    occurrences = Column(Integer, default=0)
    success_rate = Column(Numeric(5, 2), default=0)
    avg_pnl = Column(Numeric(10, 2), default=0)
    
    # Confidence
    confidence_score = Column(Numeric(3, 2), default=0)
    
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
    buying_power = Column(Numeric(15, 2))
    
    # P&L
    daily_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    
    # P&L Attribution
    delta_pnl = Column(Numeric(15, 2), default=0)
    gamma_pnl = Column(Numeric(15, 2), default=0)
    theta_pnl = Column(Numeric(15, 2), default=0)
    vega_pnl = Column(Numeric(15, 2), default=0)
    unexplained_pnl = Column(Numeric(15, 2), default=0)
    
    # Greeks snapshot
    portfolio_delta = Column(Numeric(10, 4))
    portfolio_gamma = Column(Numeric(10, 6))
    portfolio_theta = Column(Numeric(10, 4))
    portfolio_vega = Column(Numeric(10, 4))
    
    # Risk metrics
    var_1d_95 = Column(Numeric(15, 2))
    var_1d_99 = Column(Numeric(15, 2))
    
    # Metrics
    num_positions = Column(Integer, default=0)
    num_trades = Column(Integer, default=0)
    num_open_trades = Column(Integer, default=0)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    portfolio = relationship("PortfolioORM", back_populates="daily_snapshots")


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
    option_price = Column(Numeric(10, 4))
    implied_volatility = Column(Numeric(5, 4))
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============================================================================
# What-If Configuration
# ============================================================================

class WhatIfPortfolioConfigORM(Base):
    """
    Configuration for what-if portfolios.
    
    Allows different risk limits, capital assumptions, etc.
    """
    __tablename__ = 'what_if_portfolio_configs'
    
    id = Column(String(36), primary_key=True)
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    
    # Capital configuration
    simulated_capital = Column(Numeric(15, 2), nullable=False)
    simulated_buying_power = Column(Numeric(15, 2))
    margin_type = Column(String(20), default='reg_t')  # reg_t, portfolio_margin
    
    # Risk limits override
    risk_limits_json = Column(JSON)  # Full risk limits as JSON
    
    # Strategy constraints
    allowed_strategies = Column(JSON)  # List of allowed strategy types
    blocked_underlyings = Column(JSON)  # List of blocked underlyings
    
    # Market data source
    market_data_source = Column(String(50), default='live')  # live, delayed, simulated
    
    # Metadata
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ============================================================================
# Market Data Cache (for offline analysis)
# ============================================================================

class MarketDataSnapshotORM(Base):
    """
    Market data snapshots for historical analysis.
    
    Captures state at a point in time for replay/backtesting.
    """
    __tablename__ = 'market_data_snapshots'
    
    __table_args__ = (
        Index('idx_market_data_symbol_time', 'symbol', 'timestamp'),
    )
    
    id = Column(String(36), primary_key=True)
    symbol = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Price
    price = Column(Numeric(10, 4), nullable=False)
    bid = Column(Numeric(10, 4))
    ask = Column(Numeric(10, 4))
    
    # Volume
    volume = Column(Integer)
    open_interest = Column(Integer)
    
    # Volatility
    implied_volatility = Column(Numeric(5, 4))
    iv_rank = Column(Numeric(5, 2))
    iv_percentile = Column(Numeric(5, 2))
    historical_volatility = Column(Numeric(5, 4))
    
    # For options
    underlying_price = Column(Numeric(10, 4))

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============================================================================
# Recommendations & Watchlists
# ============================================================================

class RecommendationORM(Base):
    """
    Trade recommendations generated by screeners or external sources.

    Lifecycle: PENDING → ACCEPTED / REJECTED / EXPIRED
    Recommendations do NOT auto-add to portfolios. User must explicitly accept.
    """
    __tablename__ = 'recommendations'

    __table_args__ = (
        Index('idx_rec_status', 'status'),
        Index('idx_rec_source', 'source'),
        Index('idx_rec_underlying', 'underlying'),
        Index('idx_rec_created', 'created_at'),
    )

    id = Column(String(36), primary_key=True)

    # Recommendation type: entry, exit, roll, adjust
    recommendation_type = Column(String(20), nullable=False, default='entry')

    # Source
    source = Column(String(50), nullable=False)  # TradeSource enum value
    screener_name = Column(String(100))

    # Trade details
    underlying = Column(String(50), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    legs = Column(JSON)  # List of leg dicts

    # Market context at recommendation time
    market_context = Column(JSON)

    # Scoring
    confidence = Column(Integer, default=5)
    rationale = Column(Text)
    risk_category = Column(String(20), default='defined')

    # Suggested portfolio
    suggested_portfolio = Column(String(100))

    # Lifecycle
    status = Column(String(20), nullable=False, default='pending')
    # Values: 'pending', 'accepted', 'rejected', 'expired'

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime)

    # Acceptance
    accepted_notes = Column(Text)
    trade_id = Column(String(36))  # Trade created from this recommendation
    portfolio_name = Column(String(100))

    # Rejection
    rejection_reason = Column(Text)

    # Exit-specific fields (for EXIT/ROLL/ADJUST recommendations)
    trade_id_to_close = Column(String(36))   # Trade this rec is about
    exit_action = Column(String(20))          # ActionType value
    exit_urgency = Column(String(20))         # immediate, today, this_week
    triggered_rules = Column(JSON)            # List of rule names

    # Scenario-based fields (populated by scenario screeners)
    scenario_template_name = Column(String(100))  # e.g. "correction_premium_sell"
    scenario_type = Column(String(50))             # "correction", "earnings", "black_swan", "arbitrage"
    trigger_conditions_met = Column(JSON)           # Dict of matched conditions
    new_legs = Column(JSON)                   # For ROLL: legs of the replacement trade


class WatchlistORM(Base):
    """
    Watchlists of symbols for screeners.

    Can be TastyTrade public watchlists (cached) or user-defined.
    """
    __tablename__ = 'watchlists'

    __table_args__ = (
        UniqueConstraint('name', 'source', name='uix_watchlist_name_source'),
        Index('idx_watchlist_source', 'source'),
    )

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    source = Column(String(50), nullable=False, default='custom')
    # Values: 'tastytrade', 'custom'

    symbols = Column(JSON, nullable=False)  # List of ticker strings
    description = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_refreshed = Column(DateTime)


# ============================================================================
# Workflow Engine Tables
# ============================================================================

class WorkflowStateORM(Base):
    """
    Persisted workflow engine state.

    Stores current state machine position, cycle count, halt info,
    and serialized shared context so the engine can resume after restart.
    """
    __tablename__ = 'workflow_state'

    id = Column(String(36), primary_key=True)
    current_state = Column(String(50), nullable=False, default='idle')
    previous_state = Column(String(50))
    last_transition_at = Column(DateTime)
    cycle_count = Column(Integer, default=0)
    halted = Column(Boolean, default=False)
    halt_reason = Column(Text)
    halt_override_rationale = Column(Text)
    context_json = Column(JSON)   # serialized shared context
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecisionLogORM(Base):
    """
    Log of every decision point presented to the user.

    Tracks time-to-decision, escalation count, and outcome
    for accountability reporting.
    """
    __tablename__ = 'decision_log'

    __table_args__ = (
        Index('idx_decision_log_type', 'decision_type'),
        Index('idx_decision_log_presented', 'presented_at'),
        Index('idx_decision_log_response', 'response'),
    )

    id = Column(String(36), primary_key=True)
    recommendation_id = Column(String(36))
    decision_type = Column(String(20))   # entry, exit, roll, override
    presented_at = Column(DateTime, nullable=False)
    responded_at = Column(DateTime)
    response = Column(String(20))        # approved, rejected, deferred, expired
    rationale = Column(Text)
    escalation_count = Column(Integer, default=0)
    time_to_decision_seconds = Column(Integer)


# ============================================================================
# Agent Visibility Tables
# ============================================================================

class AgentRunORM(Base):
    """
    Every agent execution persisted for dashboard visibility.

    One row per agent.run() call — captures timing, status, data,
    messages, metrics, and objectives.
    """
    __tablename__ = 'agent_runs'

    __table_args__ = (
        Index('idx_agent_runs_name', 'agent_name'),
        Index('idx_agent_runs_started', 'started_at'),
        Index('idx_agent_runs_cycle', 'cycle_id'),
    )

    id = Column(String(36), primary_key=True)
    agent_name = Column(String(50), nullable=False)
    cycle_id = Column(Integer)
    workflow_state = Column(String(50))
    status = Column(String(20), nullable=False)  # AgentStatus value
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)
    data_json = Column(JSON)        # AgentResult.data
    messages = Column(JSON)         # AgentResult.messages
    metrics_json = Column(JSON)     # AgentResult.metrics
    objectives = Column(JSON)       # AgentResult.objectives
    requires_human = Column(Boolean, default=False)
    human_prompt = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentObjectiveORM(Base):
    """
    Daily objectives and grades — one row per agent per day.

    Set at morning boot, graded at EOD evaluation.
    """
    __tablename__ = 'agent_objectives'

    __table_args__ = (
        Index('idx_agent_obj_name_date', 'agent_name', 'objective_date'),
    )

    id = Column(String(36), primary_key=True)
    agent_name = Column(String(50), nullable=False)
    objective_date = Column(Date, nullable=False)
    objective_text = Column(Text)
    target_metric = Column(String(50))
    target_value = Column(Integer)
    actual_value = Column(Integer)
    grade = Column(String(5))  # A, B, C, F, N/A
    gap_analysis = Column(Text)
    set_at = Column(DateTime)
    evaluated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============================================================================
# Research Snapshots (DB-backed ResearchContainer cache)
# ============================================================================

class ResearchSnapshotORM(Base):
    """
    Persisted ResearchEntry — one row per (symbol, snapshot_date).

    Enables instant cold start: engine loads from DB instead of
    calling market_analyzer library on every restart.
    """
    __tablename__ = 'research_snapshots'

    __table_args__ = (
        UniqueConstraint('symbol', 'snapshot_date', name='uix_research_symbol_date'),
        Index('idx_research_symbol', 'symbol'),
        Index('idx_research_date', 'snapshot_date'),
    )

    id = Column(String(36), primary_key=True)
    symbol = Column(String(50), nullable=False)
    snapshot_date = Column(Date, nullable=False)

    # --- Metadata ---
    name = Column(String(200))
    asset_class = Column(String(50))

    # --- Price & Technicals ---
    current_price = Column(Numeric(10, 4))
    atr = Column(Numeric(10, 4))
    atr_pct = Column(Numeric(10, 4))
    vwma_20 = Column(Numeric(10, 4))

    # RSI
    rsi_14 = Column(Numeric(10, 4))
    rsi_overbought = Column(Boolean, default=False)
    rsi_oversold = Column(Boolean, default=False)

    # Moving Averages
    sma_20 = Column(Numeric(10, 4))
    sma_50 = Column(Numeric(10, 4))
    sma_200 = Column(Numeric(10, 4))
    ema_9 = Column(Numeric(10, 4))
    ema_21 = Column(Numeric(10, 4))
    price_vs_sma_20_pct = Column(Numeric(10, 4))
    price_vs_sma_50_pct = Column(Numeric(10, 4))
    price_vs_sma_200_pct = Column(Numeric(10, 4))

    # Bollinger
    bollinger_upper = Column(Numeric(10, 4))
    bollinger_lower = Column(Numeric(10, 4))
    bollinger_pct_b = Column(Numeric(10, 4))
    bollinger_bandwidth = Column(Numeric(10, 4))

    # MACD
    macd_line = Column(Numeric(10, 4))
    macd_signal_line = Column(Numeric(10, 4))
    macd_histogram = Column(Numeric(10, 4))
    macd_bullish_cross = Column(Boolean, default=False)
    macd_bearish_cross = Column(Boolean, default=False)

    # Stochastic
    stochastic_k = Column(Numeric(10, 4))
    stochastic_d = Column(Numeric(10, 4))
    stochastic_overbought = Column(Boolean, default=False)
    stochastic_oversold = Column(Boolean, default=False)

    # Support / Resistance
    support = Column(Numeric(10, 4))
    resistance = Column(Numeric(10, 4))
    price_vs_support_pct = Column(Numeric(10, 4))
    price_vs_resistance_pct = Column(Numeric(10, 4))

    # Signals (list of dicts as JSON)
    signals = Column(JSON)

    # --- HMM Regime ---
    hmm_regime_id = Column(Integer)
    hmm_regime_label = Column(String(50))
    hmm_confidence = Column(Numeric(5, 4))
    hmm_trend_direction = Column(String(20))
    hmm_strategy_comment = Column(Text)

    # --- Fundamentals Summary ---
    long_name = Column(String(200))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Numeric(20, 2))
    beta = Column(Numeric(8, 4))
    pe_ratio = Column(Numeric(10, 4))
    forward_pe = Column(Numeric(10, 4))
    peg_ratio = Column(Numeric(10, 4))
    earnings_growth = Column(Numeric(10, 4))
    revenue_growth = Column(Numeric(10, 4))
    dividend_yield = Column(Numeric(10, 4))
    profit_margins = Column(Numeric(10, 4))
    pct_from_52w_high = Column(Numeric(10, 4))
    pct_from_52w_low = Column(Numeric(10, 4))
    next_earnings_date = Column(String(20))
    days_to_earnings = Column(Integer)

    # --- Phase (Wyckoff) ---
    phase_name = Column(String(20))             # accumulation/markup/distribution/markdown
    phase_confidence = Column(Numeric(5, 4))
    phase_description = Column(Text)
    phase_higher_highs = Column(Boolean, default=False)
    phase_higher_lows = Column(Boolean, default=False)
    phase_lower_highs = Column(Boolean, default=False)
    phase_lower_lows = Column(Boolean, default=False)
    phase_range_compression = Column(Numeric(8, 4))
    phase_volume_trend = Column(String(20))
    phase_price_vs_sma_50_pct = Column(Numeric(10, 4))

    # --- VCP (Volatility Contraction Pattern) ---
    vcp_stage = Column(String(20))              # none/forming/maturing/ready/breakout
    vcp_score = Column(Numeric(8, 4))
    vcp_contraction_count = Column(Integer)
    vcp_current_range_pct = Column(Numeric(10, 4))
    vcp_range_compression = Column(Numeric(8, 4))
    vcp_volume_trend = Column(String(20))
    vcp_pivot_price = Column(Numeric(10, 4))
    vcp_pivot_distance_pct = Column(Numeric(10, 4))
    vcp_days_in_base = Column(Integer)
    vcp_above_sma_50 = Column(Boolean, default=False)
    vcp_above_sma_200 = Column(Boolean, default=False)
    vcp_description = Column(Text)

    # --- Smart Money ---
    smart_money_score = Column(Numeric(5, 4))
    smart_money_description = Column(Text)
    unfilled_fvg_count = Column(Integer)
    active_ob_count = Column(Integer)

    # --- Phase (enhanced from PhaseService) ---
    phase_age_days = Column(Integer)
    phase_prior = Column(String(30))
    phase_cycle_completion = Column(Numeric(5, 4))
    phase_strategy_comment = Column(Text)

    # --- Opportunities ---
    opp_zero_dte_verdict = Column(String(20))
    opp_zero_dte_confidence = Column(Numeric(5, 4))
    opp_zero_dte_strategy = Column(String(100))
    opp_zero_dte_summary = Column(Text)

    opp_leap_verdict = Column(String(20))
    opp_leap_confidence = Column(Numeric(5, 4))
    opp_leap_strategy = Column(String(100))
    opp_leap_summary = Column(Text)

    opp_breakout_verdict = Column(String(20))
    opp_breakout_confidence = Column(Numeric(5, 4))
    opp_breakout_strategy = Column(String(100))
    opp_breakout_type = Column(String(20))
    opp_breakout_pivot = Column(Numeric(10, 4))
    opp_breakout_summary = Column(Text)

    opp_momentum_verdict = Column(String(20))
    opp_momentum_confidence = Column(Numeric(5, 4))
    opp_momentum_strategy = Column(String(100))
    opp_momentum_direction = Column(String(20))
    opp_momentum_summary = Column(Text)

    # --- Screening ---
    triggered_templates = Column(JSON)

    # --- Audit ---
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MacroSnapshotORM(Base):
    """
    Persisted MacroContext — one row per snapshot_date.

    Global macro calendar cached alongside research snapshots.
    """
    __tablename__ = 'macro_snapshots'

    __table_args__ = (
        UniqueConstraint('snapshot_date', name='uix_macro_date'),
    )

    id = Column(String(36), primary_key=True)
    snapshot_date = Column(Date, nullable=False)

    # Next event
    next_event_name = Column(String(200))
    next_event_date = Column(String(20))
    next_event_impact = Column(String(20))
    next_event_options_impact = Column(Text)
    days_to_next_event = Column(Integer)

    # FOMC
    next_fomc_date = Column(String(20))
    days_to_fomc = Column(Integer)

    # Event lists (JSON arrays)
    events_7d = Column(JSON)
    events_30d = Column(JSON)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)