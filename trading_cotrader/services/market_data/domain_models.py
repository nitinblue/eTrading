"""
Instrument and RiskFactor Domain Models
=======================================

Core data structures for the Market Data Container.

Mental Model:
    Position (qty: -2)
        └── Instrument (MSFT Put @500, exp 2026-02-05)
             └── RiskFactor(s): [SELF (option price), UNDERLYING (MSFT)]

Risk Factor Rules (Deterministic):
    - Stock:           [SELF]
    - Equity Option:   [SELF, UNDERLYING]
    - Futures:         [SELF]
    - Futures Option:  [SELF, UNDERLYING]  (underlying = the futures contract)
    - FX:              DEFERRED
    - FX Option:       DEFERRED
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict


class AssetType(Enum):
    """Type of tradeable instrument."""
    STOCK = "STOCK"
    EQUITY_OPTION = "EQUITY_OPTION"
    FUTURES = "FUTURES"
    FUTURES_OPTION = "FUTURES_OPTION"
    FX = "FX"                    # Deferred
    FX_OPTION = "FX_OPTION"      # Deferred


class OptionType(Enum):
    """Call or Put."""
    CALL = "CALL"
    PUT = "PUT"


class RiskFactorType(Enum):
    """
    Type of risk factor for market data subscription.
    
    SELF:       The instrument's own price (always present)
    UNDERLYING: The underlying asset's price (for options)
    """
    SELF = "SELF"
    UNDERLYING = "UNDERLYING"


@dataclass
class Greeks:
    """Sensitivity measures for an instrument or position."""
    delta: Decimal = Decimal("0")
    gamma: Decimal = Decimal("0")
    theta: Decimal = Decimal("0")
    vega: Decimal = Decimal("0")
    rho: Decimal = Decimal("0")
    timestamp: Optional[datetime] = None
    
    def __mul__(self, quantity: int) -> "Greeks":
        """Scale Greeks by position quantity."""
        return Greeks(
            delta=self.delta * quantity,
            gamma=self.gamma * quantity,
            theta=self.theta * quantity,
            vega=self.vega * quantity,
            rho=self.rho * quantity,
            timestamp=self.timestamp
        )
    
    def __add__(self, other: "Greeks") -> "Greeks":
        """Aggregate Greeks."""
        return Greeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            theta=self.theta + other.theta,
            vega=self.vega + other.vega,
            rho=self.rho + other.rho,
            timestamp=max(self.timestamp or datetime.min, other.timestamp or datetime.min)
        )


@dataclass
class RiskFactor:
    """
    A market data subscription point.
    
    Each Instrument has one or more RiskFactors that need market data.
    Example: MSFT Call option has:
        - RiskFactor(SELF, "MSFT  250207C00500000") -> option price
        - RiskFactor(UNDERLYING, "MSFT")            -> stock price
    """
    factor_type: RiskFactorType
    symbol: str                         # DXLink subscription symbol
    
    # Market data (populated by DXLink)
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    mark: Optional[Decimal] = None
    iv: Optional[Decimal] = None        # Only for options
    greeks: Optional[Greeks] = None     # Only for SELF factor on options
    
    # Subscription management
    dxlink_subscription_id: Optional[str] = None
    last_updated: Optional[datetime] = None
    
    @property
    def mid(self) -> Optional[Decimal]:
        """Mid price if bid/ask available."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.mark
    
    def update_market_data(self, bid: Decimal, ask: Decimal, mark: Decimal,
                           iv: Optional[Decimal] = None, greeks: Optional[Greeks] = None):
        """Update market data from DXLink feed."""
        self.bid = bid
        self.ask = ask
        self.mark = mark
        self.iv = iv
        self.greeks = greeks
        self.last_updated = datetime.now()


@dataclass
class Instrument:
    """
    A unique tradeable unit. 1 Leg = 1 Instrument.
    
    Examples:
        - Stock: MSFT
        - Equity Option: MSFT Put @500 exp 2026-02-05
        - Futures: /GCZ25 (Gold Dec 2025)
        - Futures Option: /GCZ25 Call @2000 exp 2025-11-25
    """
    instrument_id: str                  # Unique identifier (could be OCC symbol for options)
    ticker: str                         # Root symbol (MSFT, /GC, etc.)
    asset_type: AssetType
    
    # Option-specific fields (None for stocks/futures)
    option_type: Optional[OptionType] = None
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    
    # For options, the underlying symbol
    underlying_symbol: Optional[str] = None  # MSFT for MSFT options, /GCZ25 for futures options
    
    multiplier: int = 100               # Contract multiplier (100 for equity options, varies for futures)
    
    # Risk factors (populated by RiskFactorResolver)
    risk_factors: List[RiskFactor] = field(default_factory=list)
    
    def is_expired(self, as_of: Optional[date] = None) -> bool:
        """Check if instrument has expired."""
        if self.expiry is None:
            return False  # Stocks/futures don't expire (well, futures do but differently)
        check_date = as_of or date.today()
        return self.expiry < check_date
    
    def is_option(self) -> bool:
        """Check if this is an option (equity or futures)."""
        return self.asset_type in (AssetType.EQUITY_OPTION, AssetType.FUTURES_OPTION)
    
    def get_self_factor(self) -> Optional[RiskFactor]:
        """Get the SELF risk factor (instrument's own price)."""
        for rf in self.risk_factors:
            if rf.factor_type == RiskFactorType.SELF:
                return rf
        return None
    
    def get_underlying_factor(self) -> Optional[RiskFactor]:
        """Get the UNDERLYING risk factor (for options)."""
        for rf in self.risk_factors:
            if rf.factor_type == RiskFactorType.UNDERLYING:
                return rf
        return None
    
    @property
    def current_price(self) -> Optional[Decimal]:
        """Current mark price of this instrument."""
        self_factor = self.get_self_factor()
        return self_factor.mark if self_factor else None
    
    @property
    def greeks(self) -> Optional[Greeks]:
        """Greeks for this instrument (from SELF factor)."""
        self_factor = self.get_self_factor()
        return self_factor.greeks if self_factor else None
    
    def days_to_expiry(self, as_of: Optional[date] = None) -> Optional[int]:
        """Days until expiration."""
        if self.expiry is None:
            return None
        check_date = as_of or date.today()
        return (self.expiry - check_date).days


class RiskFactorResolver:
    """
    Determines which RiskFactors an Instrument needs.
    
    This is deterministic based on asset type:
        - Stock:          [SELF]
        - Equity Option:  [SELF, UNDERLYING]
        - Futures:        [SELF]
        - Futures Option: [SELF, UNDERLYING]
        - FX/FX Option:   NotImplementedError (deferred)
    """
    
    @staticmethod
    def resolve(instrument: Instrument) -> List[RiskFactor]:
        """
        Generate the RiskFactors needed for an instrument.
        
        Returns list of RiskFactor objects (without market data - that comes from DXLink).
        """
        factors = []
        
        # SELF factor - always present
        factors.append(RiskFactor(
            factor_type=RiskFactorType.SELF,
            symbol=instrument.instrument_id
        ))
        
        # UNDERLYING factor - for options
        if instrument.asset_type == AssetType.EQUITY_OPTION:
            if not instrument.underlying_symbol:
                raise ValueError(f"Equity option {instrument.instrument_id} missing underlying_symbol")
            factors.append(RiskFactor(
                factor_type=RiskFactorType.UNDERLYING,
                symbol=instrument.underlying_symbol
            ))
            
        elif instrument.asset_type == AssetType.FUTURES_OPTION:
            if not instrument.underlying_symbol:
                raise ValueError(f"Futures option {instrument.instrument_id} missing underlying_symbol")
            factors.append(RiskFactor(
                factor_type=RiskFactorType.UNDERLYING,
                symbol=instrument.underlying_symbol  # This is the futures contract symbol
            ))
            
        elif instrument.asset_type in (AssetType.FX, AssetType.FX_OPTION):
            raise NotImplementedError(
                f"FX instruments deferred. Asset type: {instrument.asset_type}. "
                "Will implement when FX trading is active."
            )
        
        # Stock and Futures only have SELF - no additional factors needed
        
        return factors


@dataclass
class InstrumentRegistry:
    """
    Central store for all active instruments.
    
    Responsibilities:
        - Track unique instruments across all positions
        - Manage RiskFactor resolution
        - Cleanup expired instruments
        - Provide lookup by ID
    """
    instruments: Dict[str, Instrument] = field(default_factory=dict)
    
    def register(self, instrument: Instrument) -> Instrument:
        """
        Register an instrument. If already registered, return existing.
        Also resolves and attaches RiskFactors.
        """
        if instrument.instrument_id in self.instruments:
            return self.instruments[instrument.instrument_id]
        
        # Resolve risk factors
        instrument.risk_factors = RiskFactorResolver.resolve(instrument)
        
        self.instruments[instrument.instrument_id] = instrument
        return instrument
    
    def unregister(self, instrument_id: str) -> Optional[Instrument]:
        """Remove an instrument from the registry."""
        return self.instruments.pop(instrument_id, None)
    
    def get_by_id(self, instrument_id: str) -> Optional[Instrument]:
        """Look up instrument by ID."""
        return self.instruments.get(instrument_id)
    
    def get_all_risk_factors(self) -> List[RiskFactor]:
        """Get all unique risk factors across all instruments (for DXLink subscription)."""
        seen_symbols = set()
        factors = []
        for inst in self.instruments.values():
            for rf in inst.risk_factors:
                if rf.symbol not in seen_symbols:
                    seen_symbols.add(rf.symbol)
                    factors.append(rf)
        return factors
    
    def cleanup_expired(self, as_of: Optional[date] = None) -> List[Instrument]:
        """Remove expired instruments. Returns list of removed instruments."""
        check_date = as_of or date.today()
        expired = [inst for inst in self.instruments.values() if inst.is_expired(check_date)]
        for inst in expired:
            del self.instruments[inst.instrument_id]
        return expired
    
    def get_instruments_by_underlying(self, underlying_symbol: str) -> List[Instrument]:
        """Get all instruments for a given underlying (for hedging)."""
        return [
            inst for inst in self.instruments.values()
            if inst.underlying_symbol == underlying_symbol or inst.ticker == underlying_symbol
        ]
    
    @property
    def count(self) -> int:
        """Number of registered instruments."""
        return len(self.instruments)


# =============================================================================
# Factory functions for creating instruments from broker data
# =============================================================================

def create_stock_instrument(ticker: str) -> Instrument:
    """Create a stock instrument."""
    return Instrument(
        instrument_id=ticker,
        ticker=ticker,
        asset_type=AssetType.STOCK,
        multiplier=1
    )


def create_equity_option_instrument(
    occ_symbol: str,
    ticker: str,
    option_type: OptionType,
    strike: Decimal,
    expiry: date,
    multiplier: int = 100
) -> Instrument:
    """Create an equity option instrument."""
    return Instrument(
        instrument_id=occ_symbol,
        ticker=ticker,
        asset_type=AssetType.EQUITY_OPTION,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        underlying_symbol=ticker,
        multiplier=multiplier
    )


def create_futures_instrument(
    symbol: str,
    ticker: str,
    multiplier: int,
    expiry: Optional[date] = None
) -> Instrument:
    """Create a futures instrument."""
    return Instrument(
        instrument_id=symbol,
        ticker=ticker,
        asset_type=AssetType.FUTURES,
        expiry=expiry,
        multiplier=multiplier
    )


def create_futures_option_instrument(
    occ_symbol: str,
    ticker: str,
    futures_symbol: str,
    option_type: OptionType,
    strike: Decimal,
    expiry: date,
    multiplier: int
) -> Instrument:
    """Create a futures option instrument."""
    return Instrument(
        instrument_id=occ_symbol,
        ticker=ticker,
        asset_type=AssetType.FUTURES_OPTION,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        underlying_symbol=futures_symbol,  # The futures contract, e.g., /GCZ25
        multiplier=multiplier
    )


# =============================================================================
# Example usage
# =============================================================================

if __name__ == "__main__":
    from decimal import Decimal
    from datetime import date
    
    # Create registry
    registry = InstrumentRegistry()
    
    # Register a stock
    msft_stock = create_stock_instrument("MSFT")
    registry.register(msft_stock)
    print(f"Stock: {msft_stock.instrument_id}, Risk Factors: {[rf.factor_type.value for rf in msft_stock.risk_factors]}")
    
    # Register an equity option
    msft_put = create_equity_option_instrument(
        occ_symbol="MSFT  260205P00500000",
        ticker="MSFT",
        option_type=OptionType.PUT,
        strike=Decimal("500"),
        expiry=date(2026, 2, 5)
    )
    registry.register(msft_put)
    print(f"Equity Option: {msft_put.instrument_id}, Risk Factors: {[rf.factor_type.value for rf in msft_put.risk_factors]}")
    print(f"  Underlying symbol: {msft_put.underlying_symbol}")
    
    # Register a futures contract
    gc_futures = create_futures_instrument(
        symbol="/GCZ25",
        ticker="/GC",
        multiplier=100,
        expiry=date(2025, 12, 27)
    )
    registry.register(gc_futures)
    print(f"Futures: {gc_futures.instrument_id}, Risk Factors: {[rf.factor_type.value for rf in gc_futures.risk_factors]}")
    
    # Register a futures option
    gc_call = create_futures_option_instrument(
        occ_symbol="./GCZ25C2000",
        ticker="/GC",
        futures_symbol="/GCZ25",
        option_type=OptionType.CALL,
        strike=Decimal("2000"),
        expiry=date(2025, 11, 25),
        multiplier=100
    )
    registry.register(gc_call)
    print(f"Futures Option: {gc_call.instrument_id}, Risk Factors: {[rf.factor_type.value for rf in gc_call.risk_factors]}")
    print(f"  Underlying (futures): {gc_call.underlying_symbol}")
    
    # Summary
    print(f"\nRegistry contains {registry.count} instruments")
    print(f"Total unique risk factors to subscribe: {len(registry.get_all_risk_factors())}")
    
    # Check expiry
    print(f"\nMSFT Put expires: {msft_put.expiry}, DTE: {msft_put.days_to_expiry()}")
    print(f"Is expired? {msft_put.is_expired()}")
