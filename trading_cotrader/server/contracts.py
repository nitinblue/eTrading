"""
Institutional Trading Data Contracts

These define the shape of data flowing from backend to UI.
Implementation-agnostic: works with refresh or streaming.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from decimal import Decimal
from datetime import datetime
from enum import Enum


# ============================================================================
# MARKET CONTEXT - Macro/Market-wide data
# ============================================================================

@dataclass
class Quote:
    """Basic quote for any instrument"""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    change: Decimal          # Absolute change from prior close
    change_pct: Decimal      # Percent change
    volume: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


@dataclass
class IndexQuote(Quote):
    """Equity index quote"""
    high: Decimal = Decimal('0')
    low: Decimal = Decimal('0')
    prior_close: Decimal = Decimal('0')


@dataclass 
class RateQuote:
    """Interest rate / yield quote"""
    symbol: str              # US10Y, US02Y, etc.
    yield_pct: Decimal       # Current yield (e.g., 4.52)
    change_bp: Decimal       # Change in basis points
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass(kw_only=True)
class FuturesQuote(Quote):
    contract: str
    expiry: str
    open_interest: int = 0


@dataclass
class VolatilityQuote:
    """Volatility index quote"""
    symbol: str              # VIX, VIX9D, VVIX, SKEW, MOVE
    value: Decimal
    change: Decimal
    change_pct: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # VIX-specific
    term_structure: Optional[str] = None  # "contango" | "backwardation"


@dataclass
class FXQuote:
    """Currency pair quote"""
    pair: str                # EUR/USD, USD/JPY, etc.
    rate: Decimal
    change: Decimal
    change_pct: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MarketRegime(Enum):
    """Overall market regime classification"""
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class VolRegime(Enum):
    """Volatility regime"""
    LOW_STABLE = "low_stable"          # VIX < 15, VVIX < 90
    LOW_RISING = "low_rising"          # VIX < 15, VVIX > 100
    ELEVATED = "elevated"              # VIX 15-25
    HIGH = "high"                      # VIX 25-35
    CRISIS = "crisis"                  # VIX > 35


class CurveRegime(Enum):
    """Yield curve regime"""
    STEEP = "steep"                    # 2s10s > 100bp (expansion)
    NORMAL = "normal"                  # 2s10s 0-100bp
    FLAT = "flat"                      # 2s10s -25bp to 0
    INVERTED = "inverted"              # 2s10s < -25bp (recession warning)


@dataclass
class MarketContext:
    """
    Complete market context - the "weather" for trading
    
    This sits at the top of the screen, always visible
    """
    timestamp: datetime
    
    # Equity Indices
    indices: Dict[str, IndexQuote]     # SPY, QQQ, IWM, DIA
    
    # Rates & Bonds
    rates: Dict[str, RateQuote]        # US02Y, US10Y, US30Y
    curve_2s10s: Decimal               # 2s10s spread in bp
    move_index: Decimal                # MOVE index (bond vol)
    
    # Commodities
    commodities: Dict[str, FuturesQuote]  # /GC, /CL, /SI, /NG
    
    # Volatility Complex
    vix: VolatilityQuote
    vix9d: Optional[VolatilityQuote] = None
    vvix: Optional[VolatilityQuote] = None
    skew: Optional[VolatilityQuote] = None
    vix_term_structure: str = "contango"  # contango | backwardation
    
    # FX
    dxy: Decimal = Decimal('0')        # Dollar index
    fx_pairs: Dict[str, FXQuote] = field(default_factory=dict)  # EUR, JPY, GBP
    
    # Regime Classification (derived)
    market_regime: MarketRegime = MarketRegime.NEUTRAL
    vol_regime: VolRegime = VolRegime.LOW_STABLE
    curve_regime: CurveRegime = CurveRegime.NORMAL
    
    def get_regime_summary(self) -> str:
        """One-line market summary"""
        return f"Market: {self.market_regime.value} | Vol: {self.vol_regime.value} | Curve: {self.curve_regime.value}"


# ============================================================================
# POSITION & GREEKS - Your exposure
# ============================================================================

@dataclass
class PositionGreeks:
    """Greeks for a single position (already multiplied by quantity)"""
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')      # Daily theta in $
    vega: Decimal = Decimal('0')       # $ per 1pt IV move
    rho: Decimal = Decimal('0')
    
    # Second-order (optional, for advanced)
    vanna: Decimal = Decimal('0')      # d(delta)/d(vol)
    charm: Decimal = Decimal('0')      # d(delta)/d(time)
    volga: Decimal = Decimal('0')      # d(vega)/d(vol)


@dataclass
class PositionWithMarket:
    """
    A position enriched with live market data
    
    This is what the positions grid displays
    """
    # Identity
    position_id: str
    symbol: str                        # Underlying ticker
    
    # Option specifics (None for stock)
    option_type: Optional[str] = None  # CALL | PUT
    strike: Optional[Decimal] = None
    expiry: Optional[str] = None       # "2026-01-31"
    dte: Optional[int] = None          # Days to expiry
    
    # Position
    quantity: int = 0                  # Signed: negative = short
    
    # Prices
    entry_price: Decimal = Decimal('0')
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
    last: Decimal = Decimal('0')
    mark: Decimal = Decimal('0')       # Mid price
    
    # Greeks (position-level, already * quantity)
    greeks: PositionGreeks = field(default_factory=PositionGreeks)
    iv: Decimal = Decimal('0')         # Implied volatility
    
    # P&L
    entry_value: Decimal = Decimal('0')    # What you paid/received
    market_value: Decimal = Decimal('0')   # Current value
    unrealized_pnl: Decimal = Decimal('0')
    unrealized_pnl_pct: Decimal = Decimal('0')
    
    # P&L Attribution (how much came from each greek)
    pnl_from_delta: Decimal = Decimal('0')
    pnl_from_gamma: Decimal = Decimal('0')
    pnl_from_theta: Decimal = Decimal('0')
    pnl_from_vega: Decimal = Decimal('0')
    pnl_unexplained: Decimal = Decimal('0')
    
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
            return f"{self.symbol} {self.expiry} {self.strike}{self.option_type[0]}"
        return self.symbol


# ============================================================================
# RISK AGGREGATION - Portfolio-level view
# ============================================================================

@dataclass
class RiskBucket:
    """
    Aggregated risk for one underlying (or the whole portfolio)
    
    This is the institutional view: "What's my SPY exposure?"
    """
    underlying: str                    # "SPY" or "PORTFOLIO" for total
    
    # Aggregated Greeks
    delta: Decimal = Decimal('0')      # Net delta (contracts or shares)
    delta_dollars: Decimal = Decimal('0')  # Delta * spot price
    gamma: Decimal = Decimal('0')
    gamma_dollars: Decimal = Decimal('0')  # $ P&L for 1% move (gamma effect)
    theta: Decimal = Decimal('0')      # Daily theta in $
    vega: Decimal = Decimal('0')       # $ per 1pt IV change
    
    # Position count
    position_count: int = 0
    long_count: int = 0
    short_count: int = 0
    
    # Notional exposure
    gross_exposure: Decimal = Decimal('0')   # |long| + |short|
    net_exposure: Decimal = Decimal('0')     # long - short
    
    # By expiry (for term structure view)
    delta_by_expiry: Dict[str, Decimal] = field(default_factory=dict)
    theta_by_expiry: Dict[str, Decimal] = field(default_factory=dict)
    vega_by_expiry: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class RiskLimit:
    """A single risk limit"""
    metric: str                        # "delta", "gamma", "vega", etc.
    underlying: str                    # "SPY", "QQQ", or "PORTFOLIO"
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    
    def is_breached(self, current_value: Decimal) -> bool:
        if self.min_value is not None and current_value < self.min_value:
            return True
        if self.max_value is not None and current_value > self.max_value:
            return True
        return False
    
    def breach_amount(self, current_value: Decimal) -> Decimal:
        """How far outside the limit are we?"""
        if self.min_value is not None and current_value < self.min_value:
            return current_value - self.min_value  # Negative
        if self.max_value is not None and current_value > self.max_value:
            return current_value - self.max_value  # Positive
        return Decimal('0')


@dataclass
class LimitBreach:
    """A limit that has been breached"""
    limit: RiskLimit
    current_value: Decimal
    breach_amount: Decimal
    severity: Literal["warning", "breach", "critical"]
    suggested_action: str              # "Reduce SPY delta by 100"


# ============================================================================
# HEDGING
# ============================================================================

class HedgeInstrument(Enum):
    """What to hedge with"""
    STOCK = "stock"
    ATM_CALL = "atm_call"
    ATM_PUT = "atm_put"
    ATM_STRADDLE = "atm_straddle"
    FUTURE = "future"


@dataclass
class HedgeRecommendation:
    """A suggested hedge trade"""
    underlying: str
    instrument: HedgeInstrument
    action: Literal["buy", "sell"]
    quantity: int
    estimated_price: Decimal
    estimated_cost: Decimal            # Positive = cost, negative = credit
    
    # What this hedge fixes
    delta_impact: Decimal = Decimal('0')
    gamma_impact: Decimal = Decimal('0')
    vega_impact: Decimal = Decimal('0')
    
    # Resulting position after hedge
    resulting_delta: Decimal = Decimal('0')
    
    rationale: str = ""                # "Neutralize SPY delta"


# ============================================================================
# SCENARIO ANALYSIS
# ============================================================================

@dataclass
class ScenarioResult:
    """P&L under a specific scenario"""
    scenario_name: str                 # "SPY -2%", "VIX +5pt"
    pnl: Decimal
    pnl_pct: Decimal
    
    # Breakdown
    pnl_from_delta: Decimal = Decimal('0')
    pnl_from_gamma: Decimal = Decimal('0')
    pnl_from_vega: Decimal = Decimal('0')
    pnl_from_theta: Decimal = Decimal('0')


@dataclass
class ScenarioMatrix:
    """
    P&L across multiple scenarios
    
    Rows: spot price moves
    Columns: vol moves (or time)
    """
    underlying: str
    spot_scenarios: List[Decimal]      # [-2%, -1%, 0, +1%, +2%]
    vol_scenarios: List[Decimal]       # [-2pt, -1pt, 0, +1pt, +2pt]
    
    # Matrix of P&L values [spot_index][vol_index]
    pnl_matrix: List[List[Decimal]] = field(default_factory=list)


# ============================================================================
# THE MASTER SNAPSHOT - Everything UI needs
# ============================================================================

@dataclass
class MarketSnapshot:
    """
    Complete snapshot of everything the UI needs
    
    This is returned by GET /snapshot
    One object, one fetch, complete picture
    """
    timestamp: datetime
    
    # Market Context (macro)
    market: MarketContext
    
    # Your positions with live data
    positions: List[PositionWithMarket]
    
    # Aggregated risk by underlying
    risk_by_underlying: Dict[str, RiskBucket]
    
    # Portfolio totals
    portfolio_risk: RiskBucket         # Underlying = "PORTFOLIO"
    
    # Limit monitoring
    limits: List[RiskLimit]
    breaches: List[LimitBreach]
    
    # Hedging suggestions (only if breaches exist)
    hedge_recommendations: List[HedgeRecommendation]
    
    # Scenario analysis
    scenarios: Dict[str, ScenarioMatrix]  # By underlying
    
    # Account
    account_value: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    margin_used: Decimal = Decimal('0')
    
    # Metadata
    data_source: str = "tastytrade"    # For debugging
    is_live: bool = False              # True if streaming, False if refresh
    refresh_count: int = 0             # How many times refreshed this session


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_empty_snapshot() -> MarketSnapshot:
    """Create an empty snapshot (for initialization)"""
    return MarketSnapshot(
        timestamp=datetime.utcnow(),
        market=MarketContext(
            timestamp=datetime.utcnow(),
            indices={},
            rates={},
            curve_2s10s=Decimal('0'),
            move_index=Decimal('0'),
            commodities={},
            vix=VolatilityQuote(symbol="VIX", value=Decimal('0'), change=Decimal('0'), change_pct=Decimal('0')),
        ),
        positions=[],
        risk_by_underlying={},
        portfolio_risk=RiskBucket(underlying="PORTFOLIO"),
        limits=[],
        breaches=[],
        hedge_recommendations=[],
        scenarios={},
    )


def create_default_limits() -> List[RiskLimit]:
    """Create sensible default risk limits"""
    return [
        # Portfolio-wide
        RiskLimit(metric="delta", underlying="PORTFOLIO", min_value=Decimal('-500'), max_value=Decimal('500')),
        RiskLimit(metric="gamma", underlying="PORTFOLIO", min_value=Decimal('-100'), max_value=Decimal('100')),
        RiskLimit(metric="vega", underlying="PORTFOLIO", min_value=Decimal('-10000'), max_value=Decimal('10000')),
        RiskLimit(metric="theta", underlying="PORTFOLIO", min_value=Decimal('-500'), max_value=None),  # Theta should be positive
        
        # Per-underlying (SPY)
        RiskLimit(metric="delta", underlying="SPY", min_value=Decimal('-200'), max_value=Decimal('200')),
        RiskLimit(metric="delta", underlying="QQQ", min_value=Decimal('-150'), max_value=Decimal('150')),
    ]
