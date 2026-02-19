"""
Enhanced Domain Models - Immutable Objects with DAG Support

DESIGN PRINCIPLES:
1. Objects over values - Everything is a first-class object
2. Immutable snapshots - State captured at points in time
3. DAG-ready - Dependencies are explicit, changes propagate
4. WhatIf as Trade - WhatIf trades have same capabilities as real trades
5. P&L Attribution - Explain P&L by Greek (delta, theta, vega, unexplained)

USAGE:
    # Create a what-if portfolio
    what_if_portfolio = Portfolio.create_what_if("0DTE Strategies", capital=10000)
    
    # Create a what-if trade (same as real trade)
    trade = Trade.create_what_if(
        underlying="SPY",
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[...],
        portfolio_id=what_if_portfolio.id
    )
    
    # Track Greeks evolution
    position.record_greeks_snapshot()  # Creates GreeksSnapshot
    
    # Get P&L attribution
    attribution = position.get_pnl_attribution()
    print(f"Delta P&L: ${attribution.delta_pnl}")
    print(f"Theta P&L: ${attribution.theta_pnl}")
    print(f"Unexplained: ${attribution.unexplained_pnl}")
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any, Callable, Tuple
from decimal import Decimal
import uuid
from copy import deepcopy


# ============================================================================
# Enumerations (Extended)
# ============================================================================

class PortfolioType(Enum):
    """Type of portfolio"""
    REAL = "real"              # Connected to broker
    PAPER = "paper"            # Paper trading (broker sandbox)
    WHAT_IF = "what_if"        # Pure simulation
    BACKTEST = "backtest"      # Historical backtest
    RESEARCH = "research"      # Virtual — auto-booked for ML training


class TradeType(Enum):
    """What kind of trade is this?"""
    REAL = "real"
    PAPER = "paper"
    WHAT_IF = "what_if"        # Simulated trade in what-if portfolio
    BACKTEST = "backtest"
    RESEARCH = "research"
    REPLAY = "replay"


class TradeStatus(Enum):
    """Trade lifecycle status"""
    INTENT = "intent"          # Idea, not yet evaluated
    EVALUATED = "evaluated"    # Risk-checked, ready to submit
    PENDING = "pending"        # Submitted, waiting for fill
    PARTIAL = "partial"        # Partially filled
    EXECUTED = "executed"      # Fully filled, position open
    CLOSED = "closed"          # Position closed
    ROLLED = "rolled"          # Rolled to new expiration
    REJECTED = "rejected"      # Broker rejected
    CANCELLED = "cancelled"    # User cancelled
    ABANDONED = "abandoned"    # Idea abandoned
    EXPIRED = "expired"        # Expired worthless


class AssetType(Enum):
    EQUITY = "equity"
    OPTION = "option"
    FUTURE = "future"
    CRYPTO = "crypto"
    INDEX = "index"


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


class StrategyType(Enum):
    SINGLE = "single"
    VERTICAL_SPREAD = "vertical_spread"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    CALENDAR_SPREAD = "calendar_spread"
    CALENDAR_DOUBLE_SPREAD = "calendar_double_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    COVERED_CALL = "covered_call"
    PROTECTIVE_PUT = "protective_put"
    JADE_LIZARD = "jade_lizard"
    BIG_LIZARD = "big_lizard"
    RATIO_SPREAD = "ratio_spread"
    COLLOR = "collar"
    CUSTOM = "custom"


class RiskCategory(Enum):
    """Risk classification"""
    DEFINED = "defined"        # Max loss is known
    UNDEFINED = "undefined"    # Unlimited loss potential
    MIXED = "mixed"            # Combination


class TradeSource(Enum):
    """Where did this trade originate? Used for performance attribution by source."""
    MANUAL = "manual"                      # User-originated trade
    SCREENER_VIX = "screener_vix"          # VIX regime screener
    SCREENER_IV_RANK = "screener_iv_rank"  # IV rank screener
    SCREENER_TECHNICAL = "screener_technical"  # Technical analysis screener
    SCREENER_LEAPS = "screener_leaps"      # LEAPS entry screener
    ASTROLOGY = "astrology"                # Astrology-based recommendation
    AI_RECOMMENDATION = "ai_recommendation"  # AI/ML model recommendation
    RESEARCH = "research"                  # Research-based trade
    HEDGE = "hedge"                        # Hedging recommendation
    QUANT_RESEARCH = "quant_research"      # Auto-booked by QuantResearchAgent
    RESEARCH_TEMPLATE = "research_template"  # Generic research template pipeline
    SCENARIO_CORRECTION = "scenario_correction"
    SCENARIO_EARNINGS = "scenario_earnings"
    SCENARIO_BLACK_SWAN = "scenario_black_swan"
    SCENARIO_ARBITRAGE = "scenario_arbitrage"


# ============================================================================
# Value Objects (Immutable)
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
    multiplier: int = 100  # Default 100 for options
    
    def __post_init__(self):
        if self.asset_type == AssetType.OPTION:
            if not all([self.option_type, self.strike, self.expiration]):
                raise ValueError("Options must have option_type, strike, and expiration")
    
    @property
    def is_option(self) -> bool:
        return self.asset_type == AssetType.OPTION
    
    @property
    def is_call(self) -> bool:
        return self.option_type == OptionType.CALL
    
    @property
    def is_put(self) -> bool:
        return self.option_type == OptionType.PUT
    
    def days_to_expiration(self, as_of: datetime = None) -> Optional[int]:
        """Days until expiration"""
        if not self.expiration:
            return None
        as_of = as_of or datetime.utcnow()
        return max(0, (self.expiration - as_of).days)
    
    def is_itm(self, underlying_price: Decimal) -> bool:
        """Check if option is in-the-money"""
        if not self.is_option:
            return False
        if self.is_call:
            return underlying_price > self.strike
        return underlying_price < self.strike
    
    def moneyness(self, underlying_price: Decimal) -> Decimal:
        """Return moneyness (S/K for calls, K/S for puts)"""
        if not self.is_option or not underlying_price:
            return Decimal('1')
        if self.is_call:
            return underlying_price / self.strike
        return self.strike / underlying_price


@dataclass(frozen=True)
class Greeks:
    """
    Immutable Greeks snapshot.
    
    Can represent:
    - Per-contract Greeks (from pricing model)
    - Position Greeks (multiplied by quantity and multiplier)
    - Portfolio Greeks (sum of all positions)
    """
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    rho: Decimal = Decimal('0')
    
    # Optional: IV at time of snapshot
    implied_volatility: Optional[Decimal] = None
    
    # Timestamp of this snapshot
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __add__(self, other: 'Greeks') -> 'Greeks':
        """Add two Greeks together (for aggregation)"""
        return Greeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            theta=self.theta + other.theta,
            vega=self.vega + other.vega,
            rho=self.rho + other.rho,
            timestamp=datetime.utcnow()
        )
    
    def __sub__(self, other: 'Greeks') -> 'Greeks':
        """Subtract Greeks (for changes)"""
        return Greeks(
            delta=self.delta - other.delta,
            gamma=self.gamma - other.gamma,
            theta=self.theta - other.theta,
            vega=self.vega - other.vega,
            rho=self.rho - other.rho,
            timestamp=datetime.utcnow()
        )
    
    def scale(self, factor: Decimal) -> 'Greeks':
        """Scale Greeks by a factor (e.g., quantity)"""
        return Greeks(
            delta=self.delta * factor,
            gamma=self.gamma * factor,
            theta=self.theta * factor,
            vega=self.vega * factor,
            rho=self.rho * factor,
            implied_volatility=self.implied_volatility,
            timestamp=self.timestamp
        )
    
    def to_dict(self) -> Dict:
        return {
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
            'rho': float(self.rho),
            'iv': float(self.implied_volatility) if self.implied_volatility else None,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass(frozen=True)
class MarketData:
    """
    Immutable market data snapshot.
    
    Used for:
    - Current pricing
    - What-if scenarios (change price/IV)
    - Historical analysis
    """
    symbol: str
    price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    
    # Volatility
    implied_volatility: Optional[Decimal] = None
    iv_rank: Optional[Decimal] = None
    iv_percentile: Optional[Decimal] = None
    historical_volatility: Optional[Decimal] = None
    
    # Volume
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    
    # Underlying (for options)
    underlying_price: Optional[Decimal] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def mid_price(self) -> Decimal:
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return self.price
    
    @property
    def spread(self) -> Optional[Decimal]:
        if self.bid and self.ask:
            return self.ask - self.bid
        return None
    
    def with_price(self, new_price: Decimal) -> 'MarketData':
        """Create new MarketData with different price (for scenarios)"""
        return MarketData(
            symbol=self.symbol,
            price=new_price,
            bid=self.bid,
            ask=self.ask,
            implied_volatility=self.implied_volatility,
            iv_rank=self.iv_rank,
            iv_percentile=self.iv_percentile,
            underlying_price=self.underlying_price,
            timestamp=datetime.utcnow()
        )
    
    def with_iv(self, new_iv: Decimal) -> 'MarketData':
        """Create new MarketData with different IV (for scenarios)"""
        return MarketData(
            symbol=self.symbol,
            price=self.price,
            bid=self.bid,
            ask=self.ask,
            implied_volatility=new_iv,
            iv_rank=self.iv_rank,
            iv_percentile=self.iv_percentile,
            underlying_price=self.underlying_price,
            timestamp=datetime.utcnow()
        )


@dataclass(frozen=True)
class PnLAttribution:
    """
    P&L breakdown by Greek.
    
    Explains where P&L came from:
    - Delta P&L: From underlying price movement
    - Gamma P&L: From delta changing as price moves
    - Theta P&L: From time decay
    - Vega P&L: From IV changes
    - Unexplained: What the model can't explain
    """
    # Attribution components
    delta_pnl: Decimal = Decimal('0')
    gamma_pnl: Decimal = Decimal('0')
    theta_pnl: Decimal = Decimal('0')
    vega_pnl: Decimal = Decimal('0')
    rho_pnl: Decimal = Decimal('0')
    
    # What we can't explain
    unexplained_pnl: Decimal = Decimal('0')
    
    # Totals
    model_pnl: Decimal = Decimal('0')      # Sum of Greek P&Ls
    actual_pnl: Decimal = Decimal('0')      # Actual P&L from broker
    
    # Market changes that drove P&L
    underlying_change: Decimal = Decimal('0')
    iv_change: Decimal = Decimal('0')
    time_passed_days: Decimal = Decimal('0')
    
    # Period
    from_timestamp: Optional[datetime] = None
    to_timestamp: Optional[datetime] = None
    
    @property
    def total_model_pnl(self) -> Decimal:
        return self.delta_pnl + self.gamma_pnl + self.theta_pnl + self.vega_pnl + self.rho_pnl
    
    @property
    def attribution_error(self) -> Decimal:
        """Difference between model and actual"""
        return self.actual_pnl - self.total_model_pnl
    
    def to_dict(self) -> Dict:
        return {
            'delta_pnl': float(self.delta_pnl),
            'gamma_pnl': float(self.gamma_pnl),
            'theta_pnl': float(self.theta_pnl),
            'vega_pnl': float(self.vega_pnl),
            'unexplained_pnl': float(self.unexplained_pnl),
            'actual_pnl': float(self.actual_pnl),
            'underlying_change': float(self.underlying_change),
            'iv_change': float(self.iv_change),
        }


@dataclass(frozen=True)
class RiskMetrics:
    """
    Portfolio/Position risk metrics snapshot.
    
    Immutable snapshot of risk state.
    """
    # VaR metrics
    var_1d_95: Decimal = Decimal('0')       # 1-day 95% VaR
    var_1d_99: Decimal = Decimal('0')       # 1-day 99% VaR
    var_10d_95: Decimal = Decimal('0')      # 10-day 95% VaR
    
    # Expected shortfall (CVaR)
    cvar_1d_95: Decimal = Decimal('0')
    
    # Greeks-based risk
    delta_dollars: Decimal = Decimal('0')   # Dollar delta
    gamma_dollars: Decimal = Decimal('0')   # Dollar gamma
    vega_dollars: Decimal = Decimal('0')    # Dollar vega
    theta_dollars: Decimal = Decimal('0')   # Dollar theta (daily)
    
    # Concentration
    largest_position_pct: Decimal = Decimal('0')
    top_5_concentration_pct: Decimal = Decimal('0')
    
    # Liquidity
    days_to_liquidate: Decimal = Decimal('0')
    illiquid_positions_pct: Decimal = Decimal('0')
    
    # Margin
    margin_used: Decimal = Decimal('0')
    margin_available: Decimal = Decimal('0')
    margin_utilization_pct: Decimal = Decimal('0')
    
    # Beta
    portfolio_beta: Decimal = Decimal('1')
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            'var_1d_95': float(self.var_1d_95),
            'var_1d_99': float(self.var_1d_99),
            'delta_dollars': float(self.delta_dollars),
            'theta_dollars': float(self.theta_dollars),
            'margin_utilization_pct': float(self.margin_utilization_pct),
        }


# ============================================================================
# Core Entities
# ============================================================================

@dataclass
class Leg:
    """
    A single leg in a trade.
    
    Tracks both opening and current state for P&L attribution.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    quantity: int = 0  # Positive = long, Negative = short
    side: OrderSide = None
    
    # === OPENING STATE (immutable after fill) ===
    entry_price: Optional[Decimal] = None
    entry_time: Optional[datetime] = None
    entry_greeks: Optional[Greeks] = None
    entry_underlying_price: Optional[Decimal] = None
    entry_iv: Optional[Decimal] = None
    
    # === CURRENT STATE (updates with market) ===
    current_price: Optional[Decimal] = None
    current_greeks: Optional[Greeks] = None
    current_underlying_price: Optional[Decimal] = None
    current_iv: Optional[Decimal] = None
    
    # === EXIT STATE (filled when closed) ===
    exit_price: Optional[Decimal] = None
    exit_time: Optional[datetime] = None
    exit_greeks: Optional[Greeks] = None
    exit_underlying_price: Optional[Decimal] = None
    
    # Costs
    fees: Decimal = Decimal('0')
    commission: Decimal = Decimal('0')
    
    # Broker mapping
    broker_leg_id: Optional[str] = None
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0
    
    @property
    def is_open(self) -> bool:
        return self.exit_time is None
    
    @property
    def multiplier(self) -> int:
        return self.symbol.multiplier if self.symbol else 1
    
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L"""
        if not self.entry_price or not self.current_price:
            return Decimal('0')
        
        price_change = self.current_price - self.entry_price
        pnl = price_change * self.quantity * self.multiplier
        return pnl - self.fees - self.commission
    
    def realized_pnl(self) -> Decimal:
        """Calculate realized P&L"""
        if not self.entry_price or not self.exit_price:
            return Decimal('0')
        
        price_change = self.exit_price - self.entry_price
        pnl = price_change * self.quantity * self.multiplier
        return pnl - self.fees - self.commission
    
    def get_pnl_attribution(self) -> PnLAttribution:
        """
        Calculate P&L attribution by Greek.
        
        Uses Taylor expansion:
        P&L ≈ Δ·dS + ½Γ·dS² + Θ·dt + V·dσ + unexplained
        """
        if not self.entry_greeks or not self.entry_underlying_price:
            return PnLAttribution(actual_pnl=self.unrealized_pnl())
        
        # Price change
        dS = (self.current_underlying_price or self.entry_underlying_price) - self.entry_underlying_price
        
        # IV change
        entry_iv = self.entry_iv or Decimal('0.25')
        current_iv = self.current_iv or entry_iv
        dIV = current_iv - entry_iv
        
        # Time change (in years)
        if self.entry_time:
            dt = Decimal((datetime.utcnow() - self.entry_time).days) / Decimal('365')
        else:
            dt = Decimal('0')
        
        # Greeks (position-adjusted)
        delta = self.entry_greeks.delta * self.quantity
        gamma = self.entry_greeks.gamma * self.quantity
        theta = self.entry_greeks.theta * self.quantity  # Usually negative for long options
        vega = self.entry_greeks.vega * self.quantity
        
        # P&L components
        delta_pnl = delta * dS * self.multiplier
        gamma_pnl = Decimal('0.5') * gamma * dS * dS * self.multiplier
        theta_pnl = theta * dt * Decimal('365') * self.multiplier  # Daily theta * days
        vega_pnl = vega * dIV * Decimal('100') * self.multiplier  # Vega per 1% IV
        
        actual_pnl = self.unrealized_pnl()
        model_pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl
        unexplained = actual_pnl - model_pnl
        
        return PnLAttribution(
            delta_pnl=delta_pnl,
            gamma_pnl=gamma_pnl,
            theta_pnl=theta_pnl,
            vega_pnl=vega_pnl,
            unexplained_pnl=unexplained,
            model_pnl=model_pnl,
            actual_pnl=actual_pnl,
            underlying_change=dS,
            iv_change=dIV,
            time_passed_days=dt * Decimal('365'),
            from_timestamp=self.entry_time,
            to_timestamp=datetime.utcnow()
        )


@dataclass
class Strategy:
    """Trading strategy definition with risk parameters"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy_type: StrategyType = StrategyType.SINGLE
    
    # Risk classification
    risk_category: RiskCategory = RiskCategory.DEFINED
    
    # Risk metrics
    max_profit: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    breakeven_points: List[Decimal] = field(default_factory=list)
    
    # Target Greeks
    target_delta: Optional[Decimal] = None
    max_gamma: Optional[Decimal] = None
    target_theta: Optional[Decimal] = None
    
    # Probability metrics
    probability_of_profit: Optional[Decimal] = None
    expected_value: Optional[Decimal] = None
    
    description: Optional[str] = None
    
    # Exit rules (can be strategy-specific)
    profit_target_pct: Decimal = Decimal('50')   # Close at 50% profit
    stop_loss_pct: Decimal = Decimal('200')       # Close at 200% of credit received
    dte_exit: int = 7                              # Close at 7 DTE
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.strategy_type.value,
            'risk_category': self.risk_category.value,
            'max_profit': float(self.max_profit) if self.max_profit else None,
            'max_loss': float(self.max_loss) if self.max_loss else None,
            'profit_target_pct': float(self.profit_target_pct),
            'stop_loss_pct': float(self.stop_loss_pct),
            'dte_exit': self.dte_exit,
        }


@dataclass
class Trade:
    """
    A trade consists of one or more legs.
    
    UNIFIED MODEL: Works for both real and what-if trades.
    
    Lifecycle:
        INTENT → EVALUATED → PENDING → EXECUTED → CLOSED/ROLLED/EXPIRED
        
    What-If trades follow same lifecycle but in simulation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    legs: List[Leg] = field(default_factory=list)
    strategy: Optional[Strategy] = None
    
    # === CLASSIFICATION ===
    trade_type: TradeType = TradeType.REAL
    trade_status: TradeStatus = TradeStatus.INTENT
    
    # === PORTFOLIO LINK ===
    portfolio_id: Optional[str] = None
    underlying_symbol: str = ""
    
    # === TIMESTAMPS ===
    created_at: datetime = field(default_factory=datetime.utcnow)
    intent_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # === OPENING STATE ===
    entry_price: Optional[Decimal] = None       # Net debit/credit at entry
    entry_greeks: Optional[Greeks] = None
    entry_underlying_price: Optional[Decimal] = None
    entry_iv: Optional[Decimal] = None
    
    # === CURRENT STATE ===
    current_price: Optional[Decimal] = None
    current_greeks: Optional[Greeks] = None
    current_underlying_price: Optional[Decimal] = None
    current_iv: Optional[Decimal] = None
    
    # === EXIT STATE ===
    exit_price: Optional[Decimal] = None
    exit_greeks: Optional[Greeks] = None
    exit_reason: Optional[str] = None
    
    # === RISK MANAGEMENT ===
    planned_entry: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    profit_target: Optional[Decimal] = None
    max_risk: Optional[Decimal] = None
    
    # === EXECUTION TRACKING ===
    actual_entry: Optional[Decimal] = None
    actual_exit: Optional[Decimal] = None
    slippage: Optional[Decimal] = None
    
    # === LINKAGE ===
    intent_trade_id: Optional[str] = None       # Links executed trade to intent
    executed_trade_id: Optional[str] = None     # Links intent to executed
    rolled_from_id: Optional[str] = None        # If this is a roll
    rolled_to_id: Optional[str] = None          # If rolled out
    
    # === SOURCE TRACKING ===
    trade_source: TradeSource = TradeSource.MANUAL
    recommendation_id: Optional[str] = None  # Links to the recommendation that spawned this trade

    # === METADATA ===
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    broker_trade_id: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.trade_status in [TradeStatus.EXECUTED, TradeStatus.PARTIAL]
    
    @property
    def is_what_if(self) -> bool:
        return self.trade_type == TradeType.WHAT_IF
    
    @property
    def is_real(self) -> bool:
        return self.trade_type == TradeType.REAL
    
    # === FACTORY METHODS ===
    
    @classmethod
    def create_what_if(
        cls,
        underlying: str,
        strategy_type: StrategyType,
        legs: List[Leg],
        portfolio_id: str = None,
        strategy: Strategy = None,
        **kwargs
    ) -> 'Trade':
        """Create a what-if trade"""
        trade = cls(
            underlying_symbol=underlying,
            trade_type=TradeType.WHAT_IF,
            trade_status=TradeStatus.INTENT,
            portfolio_id=portfolio_id,
            legs=legs,
            strategy=strategy or Strategy(strategy_type=strategy_type),
            **kwargs
        )
        trade.intent_at = datetime.utcnow()
        return trade
    
    @classmethod
    def create_real(
        cls,
        underlying: str,
        strategy_type: StrategyType,
        legs: List[Leg],
        portfolio_id: str,
        **kwargs
    ) -> 'Trade':
        """Create a real trade intent"""
        trade = cls(
            underlying_symbol=underlying,
            trade_type=TradeType.REAL,
            trade_status=TradeStatus.INTENT,
            portfolio_id=portfolio_id,
            legs=legs,
            strategy=Strategy(strategy_type=strategy_type),
            **kwargs
        )
        trade.intent_at = datetime.utcnow()
        return trade
    
    # === LIFECYCLE METHODS ===
    
    def mark_evaluated(self, risk_result: Any = None):
        """Mark as evaluated (risk-checked)"""
        self.trade_status = TradeStatus.EVALUATED
        self.evaluated_at = datetime.utcnow()
    
    def mark_submitted(self, broker_order_id: str = None):
        """Mark as submitted to broker"""
        self.trade_status = TradeStatus.PENDING
        self.submitted_at = datetime.utcnow()
        if broker_order_id:
            self.broker_trade_id = broker_order_id
    
    def mark_executed(
        self,
        fill_price: Decimal,
        fill_time: datetime = None,
        greeks: Greeks = None,
        underlying_price: Decimal = None
    ):
        """Mark as executed (filled)"""
        self.trade_status = TradeStatus.EXECUTED
        self.executed_at = fill_time or datetime.utcnow()
        
        # Record opening state
        self.entry_price = fill_price
        self.actual_entry = fill_price
        self.entry_greeks = greeks
        self.entry_underlying_price = underlying_price
        
        # Calculate slippage
        if self.planned_entry:
            self.slippage = fill_price - self.planned_entry
    
    def mark_closed(
        self,
        exit_price: Decimal,
        exit_time: datetime = None,
        reason: str = None
    ):
        """Mark as closed"""
        self.trade_status = TradeStatus.CLOSED
        self.closed_at = exit_time or datetime.utcnow()
        self.exit_price = exit_price
        self.actual_exit = exit_price
        self.exit_reason = reason
    
    def mark_rolled(self, new_trade_id: str, reason: str = None):
        """Mark as rolled to new trade"""
        self.trade_status = TradeStatus.ROLLED
        self.closed_at = datetime.utcnow()
        self.rolled_to_id = new_trade_id
        self.exit_reason = reason or "Rolled"
    
    def mark_expired(self):
        """Mark as expired"""
        self.trade_status = TradeStatus.EXPIRED
        self.closed_at = datetime.utcnow()
        self.exit_price = Decimal('0')
        self.exit_reason = "Expired worthless"
    
    # === P&L METHODS ===
    
    def net_cost(self) -> Decimal:
        """Calculate net debit/credit"""
        total = Decimal('0')
        for leg in self.legs:
            if leg.entry_price:
                cost = leg.entry_price * abs(leg.quantity) * leg.multiplier
                total += cost if leg.is_long else -cost
        return total
    
    def unrealized_pnl(self) -> Decimal:
        return sum(leg.unrealized_pnl() for leg in self.legs)
    
    def realized_pnl(self) -> Decimal:
        return sum(leg.realized_pnl() for leg in self.legs)
    
    def total_pnl(self) -> Decimal:
        return self.unrealized_pnl() if self.is_open else self.realized_pnl()
    
    def total_greeks(self) -> Greeks:
        """Aggregate Greeks across all legs"""
        result = Greeks()
        for leg in self.legs:
            if leg.current_greeks:
                result = result + leg.current_greeks.scale(Decimal(leg.quantity))
        return result
    
    def get_pnl_attribution(self) -> PnLAttribution:
        """Aggregate P&L attribution across all legs"""
        attributions = [leg.get_pnl_attribution() for leg in self.legs]
        
        return PnLAttribution(
            delta_pnl=sum(a.delta_pnl for a in attributions),
            gamma_pnl=sum(a.gamma_pnl for a in attributions),
            theta_pnl=sum(a.theta_pnl for a in attributions),
            vega_pnl=sum(a.vega_pnl for a in attributions),
            unexplained_pnl=sum(a.unexplained_pnl for a in attributions),
            actual_pnl=self.total_pnl(),
            from_timestamp=self.executed_at,
            to_timestamp=datetime.utcnow()
        )
    
    def days_to_expiration(self) -> Optional[int]:
        """Days to nearest expiration"""
        dtes = [leg.symbol.days_to_expiration() for leg in self.legs if leg.symbol.expiration]
        return min(dtes) if dtes else None
    
    def to_dict(self) -> Dict:
        """Serialize for storage/display"""
        return {
            'id': self.id,
            'type': self.trade_type.value,
            'status': self.trade_status.value,
            'underlying': self.underlying_symbol,
            'strategy': self.strategy.to_dict() if self.strategy else None,
            'legs': len(self.legs),
            'entry_price': float(self.entry_price) if self.entry_price else None,
            'current_price': float(self.current_price) if self.current_price else None,
            'pnl': float(self.total_pnl()),
            'dte': self.days_to_expiration(),
            'greeks': self.total_greeks().to_dict(),
        }


@dataclass
class Position:
    """
    Current position snapshot.
    
    Tracks opening vs current state for P&L attribution.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    quantity: int = 0
    
    # === OPENING STATE ===
    entry_price: Decimal = Decimal('0')
    entry_time: Optional[datetime] = None
    entry_greeks: Optional[Greeks] = None
    entry_underlying_price: Optional[Decimal] = None
    entry_iv: Optional[Decimal] = None
    total_cost: Decimal = Decimal('0')
    
    # === CURRENT STATE ===
    current_price: Optional[Decimal] = None
    current_greeks: Optional[Greeks] = None
    current_underlying_price: Optional[Decimal] = None
    current_iv: Optional[Decimal] = None
    market_value: Decimal = Decimal('0')
    
    # === GREEKS HISTORY (for P&L attribution) ===
    greeks: List[Greeks] = field(default_factory=list)
    
    # === LINKS ===
    portfolio_id: Optional[str] = None
    trade_ids: List[str] = field(default_factory=list)
    broker_position_id: Optional[str] = None
    
    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0
    
    @property
    def multiplier(self) -> int:
        return self.symbol.multiplier if self.symbol else 1
    
    def unrealized_pnl(self) -> Decimal:
        if not self.current_price:
            return Decimal('0')
        current_value = self.current_price * self.quantity * self.multiplier
        return current_value - self.total_cost
    
    def pnl_percent(self) -> Decimal:
        if self.total_cost == 0:
            return Decimal('0')
        return (self.unrealized_pnl() / abs(self.total_cost)) * 100
    
    def record_greeks_snapshot(self):
        """Record current Greeks to history"""
        if self.current_greeks:
            self.greeks_history.append(self.current_greeks)
    
    def get_pnl_attribution(self) -> PnLAttribution:
        """Calculate P&L attribution by Greek"""
        if not self.entry_greeks or not self.entry_underlying_price:
            return PnLAttribution(actual_pnl=self.unrealized_pnl())
        
        # Similar to Leg.get_pnl_attribution
        dS = (self.current_underlying_price or self.entry_underlying_price) - self.entry_underlying_price
        
        entry_iv = self.entry_iv or Decimal('0.25')
        current_iv = self.current_iv or entry_iv
        dIV = current_iv - entry_iv
        
        if self.entry_time:
            dt = Decimal((datetime.utcnow() - self.entry_time).days) / Decimal('365')
        else:
            dt = Decimal('0')
        
        delta = self.entry_greeks.delta * self.quantity
        gamma = self.entry_greeks.gamma * self.quantity
        theta = self.entry_greeks.theta * self.quantity
        vega = self.entry_greeks.vega * self.quantity
        
        delta_pnl = delta * dS * self.multiplier
        gamma_pnl = Decimal('0.5') * gamma * dS * dS * self.multiplier
        theta_pnl = theta * dt * Decimal('365') * self.multiplier
        vega_pnl = vega * dIV * Decimal('100') * self.multiplier
        
        actual_pnl = self.unrealized_pnl()
        model_pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl
        unexplained = actual_pnl - model_pnl
        
        return PnLAttribution(
            delta_pnl=delta_pnl,
            gamma_pnl=gamma_pnl,
            theta_pnl=theta_pnl,
            vega_pnl=vega_pnl,
            unexplained_pnl=unexplained,
            model_pnl=model_pnl,
            actual_pnl=actual_pnl,
            underlying_change=dS,
            iv_change=dIV,
            time_passed_days=dt * Decimal('365'),
        )


@dataclass
class Portfolio:
    """
    Portfolio container.
    
    UNIFIED MODEL: Works for both real and what-if portfolios.
    
    What-If portfolios have configurable capital and can be used
    to simulate different strategies.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    
    # === TYPE ===
    portfolio_type: PortfolioType = PortfolioType.REAL
    
    # === BROKER (for real portfolios) ===
    broker: str = ""
    account_id: str = ""
    
    # === CAPITAL (configurable for what-if) ===
    initial_capital: Decimal = Decimal('0')     # Starting capital
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    total_equity: Decimal = Decimal('0')
    
    # === RISK LIMITS (per portfolio) ===
    max_portfolio_delta: Decimal = Decimal('500')
    max_position_size_pct: Decimal = Decimal('10')
    max_single_trade_risk_pct: Decimal = Decimal('5')
    max_total_risk_pct: Decimal = Decimal('25')
    min_cash_reserve_pct: Decimal = Decimal('10')
    
    # === GREEKS ===
    portfolio_greeks: Optional[Greeks] = None
    
    # === RISK METRICS ===
    risk_metrics: Optional[RiskMetrics] = None
    
    # === PERFORMANCE ===
    total_pnl: Decimal = Decimal('0')
    daily_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    
    # === METADATA ===
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_real(self) -> bool:
        return self.portfolio_type == PortfolioType.REAL
    
    @property
    def is_what_if(self) -> bool:
        return self.portfolio_type == PortfolioType.WHAT_IF
    
    @property
    def net_liquidating_value(self) -> Decimal:
        return self.total_equity
    
    # === FACTORY METHODS ===
    
    @classmethod
    def create_what_if(
        cls,
        name: str,
        capital: Decimal,
        description: str = "",
        risk_limits: Dict = None,
        **kwargs
    ) -> 'Portfolio':
        """Create a what-if portfolio with custom capital and limits"""
        portfolio = cls(
            name=name,
            portfolio_type=PortfolioType.WHAT_IF,
            initial_capital=Decimal(str(capital)),
            cash_balance=Decimal(str(capital)),
            buying_power=Decimal(str(capital)),
            total_equity=Decimal(str(capital)),
            description=description,
            **kwargs
        )
        
        # Apply custom risk limits
        if risk_limits:
            if 'max_delta' in risk_limits:
                portfolio.max_portfolio_delta = Decimal(str(risk_limits['max_delta']))
            if 'max_position_pct' in risk_limits:
                portfolio.max_position_size_pct = Decimal(str(risk_limits['max_position_pct']))
            if 'max_trade_risk_pct' in risk_limits:
                portfolio.max_single_trade_risk_pct = Decimal(str(risk_limits['max_trade_risk_pct']))
        
        return portfolio
    
    @classmethod
    def create_real(
        cls,
        name: str,
        broker: str,
        account_id: str,
        **kwargs
    ) -> 'Portfolio':
        """Create a real portfolio linked to broker"""
        return cls(
            name=name,
            portfolio_type=PortfolioType.REAL,
            broker=broker,
            account_id=account_id,
            **kwargs
        )
    
    @classmethod
    def create_research(
        cls,
        name: str,
        description: str = "",
        risk_limits: Dict = None,
        **kwargs
    ) -> 'Portfolio':
        """Create a virtual research portfolio for ML training data."""
        portfolio = cls(
            name=name,
            portfolio_type=PortfolioType.RESEARCH,
            initial_capital=Decimal('0'),
            cash_balance=Decimal('0'),
            buying_power=Decimal('0'),
            total_equity=Decimal('0'),
            description=description,
            **kwargs
        )
        if risk_limits:
            if 'max_delta' in risk_limits:
                portfolio.max_portfolio_delta = Decimal(str(risk_limits['max_delta']))
            if 'max_position_pct' in risk_limits:
                portfolio.max_position_size_pct = Decimal(str(risk_limits['max_position_pct']))
            if 'max_trade_risk_pct' in risk_limits:
                portfolio.max_single_trade_risk_pct = Decimal(str(risk_limits['max_trade_risk_pct']))
        return portfolio

    # === RISK METHODS ===

    def available_risk_capital(self) -> Decimal:
        """How much more risk can we take?"""
        max_risk = self.total_equity * self.max_total_risk_pct / 100
        # Would need to calculate current risk from positions
        return max_risk
    
    def delta_capacity(self) -> Decimal:
        """How much more delta can we add?"""
        current_delta = abs(self.portfolio_greeks.delta) if self.portfolio_greeks else Decimal('0')
        return self.max_portfolio_delta - current_delta
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.portfolio_type.value,
            'total_equity': float(self.total_equity),
            'cash_balance': float(self.cash_balance),
            'buying_power': float(self.buying_power),
            'total_pnl': float(self.total_pnl),
            'greeks': self.portfolio_greeks.to_dict() if self.portfolio_greeks else None,
            'risk_limits': {
                'max_delta': float(self.max_portfolio_delta),
                'max_position_pct': float(self.max_position_size_pct),
                'max_trade_risk_pct': float(self.max_single_trade_risk_pct),
            }
        }


# ============================================================================
# DAG Support - Reactive Computation
# ============================================================================

@dataclass
class ComputedValue:
    """
    A value that depends on other values.
    
    When dependencies change, this value is marked stale.
    Used for DAG-based UI updates.
    """
    value: Any = None
    dependencies: List[str] = field(default_factory=list)  # IDs of dependencies
    is_stale: bool = True
    last_computed: Optional[datetime] = None
    compute_fn: Optional[Callable] = None
    
    def mark_stale(self):
        self.is_stale = True
    
    def compute(self, context: Dict) -> Any:
        """Recompute value from dependencies"""
        if self.compute_fn:
            self.value = self.compute_fn(context)
            self.is_stale = False
            self.last_computed = datetime.utcnow()
        return self.value


@dataclass
class Cell:
    """
    A cell in the trading grid (DAG node).
    
    Can contain:
    - A Trade
    - A Position
    - A WhatIf scenario
    - A computed value
    - A market data reference
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    row: int = 0
    col: int = 0
    
    # Content type
    content_type: str = ""  # 'trade', 'position', 'what_if', 'computed', 'market_data'
    content_id: Optional[str] = None
    content: Any = None
    
    # Dependencies (other cell IDs)
    depends_on: List[str] = field(default_factory=list)
    
    # Computed value (if this is a formula cell)
    formula: Optional[str] = None
    computed_value: Optional[ComputedValue] = None
    
    # Display
    display_format: str = ""
    
    def is_stale(self) -> bool:
        if self.computed_value:
            return self.computed_value.is_stale
        return False
    
    def mark_stale(self):
        if self.computed_value:
            self.computed_value.mark_stale()


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Create a what-if portfolio for 0DTE strategies
    dte_portfolio = Portfolio.create_what_if(
        name="0DTE Strategies",
        capital=10000,
        description="Testing 0DTE iron condors",
        risk_limits={
            'max_delta': 50,
            'max_position_pct': 20,
            'max_trade_risk_pct': 10
        }
    )
    print(f"Created portfolio: {dte_portfolio.name}")
    print(f"  Capital: ${dte_portfolio.total_equity}")
    print(f"  Max Delta: {dte_portfolio.max_portfolio_delta}")
    
    # Create a what-if trade
    spy_call = Symbol(
        ticker="SPY",
        asset_type=AssetType.OPTION,
        option_type=OptionType.CALL,
        strike=Decimal('600'),
        expiration=datetime(2025, 1, 31)
    )
    
    short_leg = Leg(
        symbol=spy_call,
        quantity=-1,
        side=OrderSide.SELL_TO_OPEN,
        entry_price=Decimal('2.50'),
        entry_greeks=Greeks(delta=Decimal('-0.30'), theta=Decimal('0.05'))
    )
    
    trade = Trade.create_what_if(
        underlying="SPY",
        strategy_type=StrategyType.SINGLE,
        legs=[short_leg],
        portfolio_id=dte_portfolio.id
    )
    
    print(f"\nCreated trade: {trade.underlying_symbol}")
    print(f"  Type: {trade.trade_type.value}")
    print(f"  Status: {trade.trade_status.value}")
    print(f"  Net cost: ${trade.net_cost()}")
    
    # Simulate execution
    trade.mark_evaluated()
    trade.mark_executed(
        fill_price=Decimal('2.45'),
        greeks=Greeks(delta=Decimal('-30'), theta=Decimal('5')),
        underlying_price=Decimal('595')
    )
    
    print(f"\nAfter execution:")
    print(f"  Status: {trade.trade_status.value}")
    print(f"  Entry: ${trade.entry_price}")
    print(f"  Slippage: ${trade.slippage}")