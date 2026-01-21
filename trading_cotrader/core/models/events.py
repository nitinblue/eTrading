"""
Event Sourcing Models - Capture every decision for AI learning

Every action you take is an event that the AI can learn from.
This is the foundation of the Co-Trader system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List, Any
from decimal import Decimal
import uuid


class EventType(Enum):
    """Types of trading events"""
    # Trade lifecycle
    TRADE_OPENED = "trade_opened"
    TRADE_ADJUSTED = "trade_adjusted"
    TRADE_ROLLED = "trade_rolled"
    TRADE_CLOSED = "trade_closed"
    TRADE_HEDGED = "trade_hedged"
    
    # Risk management
    STOP_LOSS_HIT = "stop_loss_hit"
    PROFIT_TARGET_HIT = "profit_target_hit"
    POSITION_SIZED = "position_sized"
    
    # Market events
    EARNINGS_APPROACHING = "earnings_approaching"
    VOLATILITY_SPIKE = "volatility_spike"
    TECHNICAL_SIGNAL = "technical_signal"


class MarketOutlook(Enum):
    """Your market view at decision time"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class RiskTolerance(Enum):
    """Risk appetite for this trade"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class TradeOutcome(Enum):
    """How did the trade turn out?"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    ONGOING = "ongoing"


# ============================================================================
# Event Models
# ============================================================================

@dataclass
class MarketContext:
    """
    Market conditions when decision was made
    Critical for AI to understand the environment
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Underlying
    underlying_symbol: str = ""
    underlying_price: Decimal = Decimal('0')
    
    # Volatility
    vix: Optional[Decimal] = None
    iv_rank: Optional[Decimal] = None  # 0-100
    iv_percentile: Optional[Decimal] = None  # 0-100
    
    # Technical indicators
    rsi: Optional[Decimal] = None
    support_level: Optional[Decimal] = None
    resistance_level: Optional[Decimal] = None
    
    # Market regime
    market_trend: Optional[str] = None  # "uptrend", "downtrend", "sideways"
    days_to_earnings: Optional[int] = None
    
    # Greeks environment
    aggregate_put_call_ratio: Optional[Decimal] = None
    
    # Macro
    spy_price: Optional[Decimal] = None
    qqq_price: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'underlying_symbol': self.underlying_symbol,
            'underlying_price': float(self.underlying_price),
            'vix': float(self.vix) if self.vix else None,
            'iv_rank': float(self.iv_rank) if self.iv_rank else None,
            'iv_percentile': float(self.iv_percentile) if self.iv_percentile else None,
            'rsi': float(self.rsi) if self.rsi else None,
            'support_level': float(self.support_level) if self.support_level else None,
            'resistance_level': float(self.resistance_level) if self.resistance_level else None,
            'market_trend': self.market_trend,
            'days_to_earnings': self.days_to_earnings,
            'spy_price': float(self.spy_price) if self.spy_price else None,
        }


@dataclass
class DecisionContext:
    """
    WHY you made this decision
    This is what the AI learns from
    """
    # Your reasoning
    rationale: str = ""  # Free text: "IV rank at 85, expecting reversion"
    market_outlook: MarketOutlook = MarketOutlook.NEUTRAL
    confidence_level: int = 5  # 1-10 scale
    
    # Strategy intent
    time_horizon_days: int = 45  # How long you plan to hold
    profit_target_percent: Optional[Decimal] = None  # Target % gain
    max_loss_percent: Optional[Decimal] = None  # Max % loss willing to take
    
    # Risk profile
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    position_size_rationale: str = ""  # "20% of portfolio, 5% risk"
    
    # Alternatives considered
    alternatives_considered: List[str] = field(default_factory=list)
    why_chosen: str = ""  # Why this over alternatives
    
    # External factors
    influenced_by: List[str] = field(default_factory=list)  # ["news", "technical_signal", "gut_feel"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rationale': self.rationale,
            'market_outlook': self.market_outlook.value,
            'confidence_level': self.confidence_level,
            'time_horizon_days': self.time_horizon_days,
            'profit_target_percent': float(self.profit_target_percent) if self.profit_target_percent else None,
            'max_loss_percent': float(self.max_loss_percent) if self.max_loss_percent else None,
            'risk_tolerance': self.risk_tolerance.value,
            'position_size_rationale': self.position_size_rationale,
            'alternatives_considered': self.alternatives_considered,
            'why_chosen': self.why_chosen,
            'influenced_by': self.influenced_by,
        }


@dataclass
class TradeOutcomeData:
    """
    Results of the trade
    Used for reinforcement learning
    """
    outcome: TradeOutcome = TradeOutcome.ONGOING
    
    # Financial results
    final_pnl: Decimal = Decimal('0')
    pnl_percent: Decimal = Decimal('0')
    days_held: int = 0
    
    # What happened
    close_reason: str = ""  # "profit_target", "stop_loss", "time_decay", "rolled"
    met_expectations: bool = False
    
    # Learnings
    what_went_right: str = ""
    what_went_wrong: str = ""
    would_do_differently: str = ""
    
    # Greeks attribution (how much P&L came from each Greek)
    pnl_from_delta: Optional[Decimal] = None
    pnl_from_theta: Optional[Decimal] = None
    pnl_from_vega: Optional[Decimal] = None
    pnl_from_gamma: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'outcome': self.outcome.value,
            'final_pnl': float(self.final_pnl),
            'pnl_percent': float(self.pnl_percent),
            'days_held': self.days_held,
            'close_reason': self.close_reason,
            'met_expectations': self.met_expectations,
            'what_went_right': self.what_went_right,
            'what_went_wrong': self.what_went_wrong,
            'would_do_differently': self.would_do_differently,
            'pnl_from_delta': float(self.pnl_from_delta) if self.pnl_from_delta else None,
            'pnl_from_theta': float(self.pnl_from_theta) if self.pnl_from_theta else None,
            'pnl_from_vega': float(self.pnl_from_vega) if self.pnl_from_vega else None,
        }


@dataclass
class TradeEvent:
    """
    An event that occurred during trading
    This is stored in the database for AI learning
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # What happened
    event_type: EventType = EventType.TRADE_OPENED
    trade_id: str = ""
    
    # Context
    market_context: MarketContext = field(default_factory=MarketContext)
    decision_context: DecisionContext = field(default_factory=DecisionContext)
    
    # Trade details
    strategy_type: str = ""
    underlying_symbol: str = ""
    net_credit_debit: Decimal = Decimal('0')
    
    # Greeks at entry
    entry_delta: Decimal = Decimal('0')
    entry_theta: Decimal = Decimal('0')
    entry_vega: Decimal = Decimal('0')
    
    # Outcome (filled in later)
    outcome: Optional[TradeOutcomeData] = None
    
    # Metadata for searching/filtering
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'trade_id': self.trade_id,
            'market_context': self.market_context.to_dict(),
            'decision_context': self.decision_context.to_dict(),
            'strategy_type': self.strategy_type,
            'underlying_symbol': self.underlying_symbol,
            'net_credit_debit': float(self.net_credit_debit),
            'entry_delta': float(self.entry_delta),
            'entry_theta': float(self.entry_theta),
            'entry_vega': float(self.entry_vega),
            'outcome': self.outcome.to_dict() if self.outcome else None,
            'tags': self.tags,
        }


@dataclass
class AdjustmentEvent(TradeEvent):
    """
    Specific event for trade adjustments
    Captures what changed and why
    """
    original_trade_id: str = ""
    adjustment_type: str = ""  # "roll", "add_leg", "close_leg", "hedge"
    
    # What changed
    legs_added: List[Dict] = field(default_factory=list)
    legs_removed: List[Dict] = field(default_factory=list)
    
    # Greeks delta (how Greeks changed)
    delta_change: Decimal = Decimal('0')
    theta_change: Decimal = Decimal('0')
    
    def __post_init__(self):
        self.event_type = EventType.TRADE_ADJUSTED


@dataclass
class RollEvent(TradeEvent):
    """
    Rolling a position to new expiration/strikes
    """
    original_expiration: datetime = None
    new_expiration: datetime = None
    
    original_strikes: List[Decimal] = field(default_factory=list)
    new_strikes: List[Decimal] = field(default_factory=list)
    
    roll_cost_credit: Decimal = Decimal('0')  # Cost/credit to roll
    
    def __post_init__(self):
        self.event_type = EventType.TRADE_ROLLED


# ============================================================================
# Pattern Storage
# ============================================================================

@dataclass
class RecognizedPattern:
    """
    A pattern the AI has recognized in your trading
    """
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_type: str = ""  # "entry_condition", "exit_trigger", "adjustment_rule"
    
    # Pattern description
    description: str = ""  # "Open iron condor when IV rank > 70"
    
    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Statistics
    occurrences: int = 0
    success_rate: float = 0.0
    avg_pnl: Decimal = Decimal('0')
    
    # Confidence
    confidence_score: float = 0.0  # 0-1, how confident the AI is
    
    # When discovered
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)