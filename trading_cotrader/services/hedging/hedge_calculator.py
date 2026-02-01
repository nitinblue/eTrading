"""
Hedge Calculator Service
========================

Computes hedge requirements at the instrument level.

Key principle: Hedge at the risk factor level, not the strategy level.
    - If you're short delta on MSFT options, hedge with MSFT shares
    - If you're short delta on /GC options, hedge with /GC futures
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict

# Import from market_data module
from trading_cotrader.services.market_data import (
    Instrument, InstrumentRegistry, RiskFactor, RiskFactorType,
    AssetType, Greeks
)


class HedgeType(Enum):
    """Type of hedge instrument."""
    SHARES = "SHARES"           # Stock shares
    FUTURES = "FUTURES"         # Futures contracts
    OPTIONS = "OPTIONS"         # Options (for gamma/vega hedging)


@dataclass
class HedgeRecommendation:
    """
    A recommended hedge action.
    
    Example:
        To neutralize SPY delta: BUY 150 SPY shares @ $588.25
        Cost: $88,237.50
    """
    underlying_symbol: str              # What to hedge (SPY, /GC, etc.)
    hedge_type: HedgeType               # How to hedge
    
    # What to do
    quantity: int                       # Signed: positive=buy, negative=sell
    instrument_symbol: str              # Exact symbol to trade
    
    # Current market
    current_price: Optional[Decimal] = None
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    
    # Risk being hedged
    target_greek: str = "delta"         # Which greek we're hedging
    current_exposure: Decimal = Decimal("0")  # Current exposure (e.g., delta = -150)
    post_hedge_exposure: Decimal = Decimal("0")  # After hedge (should be ~0)
    
    # Cost analysis
    estimated_cost: Optional[Decimal] = None  # Total cost to execute
    
    # Optional: alternative hedges
    alternatives: List["HedgeRecommendation"] = field(default_factory=list)
    
    @property
    def action(self) -> str:
        """Human-readable action: BUY or SELL."""
        return "BUY" if self.quantity > 0 else "SELL"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "underlying": self.underlying_symbol,
            "hedge_type": self.hedge_type.value,
            "action": self.action,
            "quantity": abs(self.quantity),
            "symbol": self.instrument_symbol,
            "price": float(self.current_price) if self.current_price else None,
            "target_greek": self.target_greek,
            "current_exposure": float(self.current_exposure),
            "post_hedge_exposure": float(self.post_hedge_exposure),
            "estimated_cost": float(self.estimated_cost) if self.estimated_cost else None,
        }


@dataclass
class RiskBucket:
    """
    Aggregated risk for one underlying.
    
    Used to see total exposure to SPY, MSFT, /GC, etc.
    """
    underlying: str
    
    # Greeks (aggregated across all positions)
    delta: Decimal = Decimal("0")
    gamma: Decimal = Decimal("0")
    theta: Decimal = Decimal("0")
    vega: Decimal = Decimal("0")
    
    # Dollar exposures
    delta_dollars: Decimal = Decimal("0")   # Delta × spot × multiplier
    gamma_dollars: Decimal = Decimal("0")   # P&L from 1% move due to gamma
    
    # Position count
    position_count: int = 0
    
    # Breakdown by expiry (for term structure view)
    delta_by_expiry: Dict[str, Decimal] = field(default_factory=dict)
    theta_by_expiry: Dict[str, Decimal] = field(default_factory=dict)
    
    def add_position_greeks(self, greeks: Greeks, expiry: Optional[str] = None, quantity: int = 1):
        """Add a position's greeks to this bucket."""
        scaled = greeks * quantity
        self.delta += scaled.delta
        self.gamma += scaled.gamma
        self.theta += scaled.theta
        self.vega += scaled.vega
        self.position_count += 1
        
        if expiry:
            self.delta_by_expiry[expiry] = self.delta_by_expiry.get(expiry, Decimal("0")) + scaled.delta
            self.theta_by_expiry[expiry] = self.theta_by_expiry.get(expiry, Decimal("0")) + scaled.theta
    
    def calculate_dollar_exposures(self, underlying_price: Decimal, multiplier: int = 100):
        """Calculate dollar exposures given underlying price."""
        # Delta dollars: delta × price × multiplier
        # For a delta of 0.5 on 1 contract, if stock is $100: 0.5 × 100 × 100 = $5,000
        self.delta_dollars = self.delta * underlying_price * multiplier
        
        # Gamma dollars: P&L from 1% move = 0.5 × gamma × (price × 0.01)² × multiplier
        # Simplified: gamma_dollars ≈ 0.5 × gamma × price² × 0.0001 × multiplier
        one_percent_move = underlying_price * Decimal("0.01")
        self.gamma_dollars = Decimal("0.5") * self.gamma * (one_percent_move ** 2) * multiplier


class HedgeCalculator:
    """
    Calculates hedge recommendations.
    
    Philosophy:
        - Hedge at the instrument level, not strategy level
        - Use the simplest hedge (shares for equity, futures for futures)
        - Provide alternatives when available
    """
    
    def __init__(self, registry: InstrumentRegistry):
        self.registry = registry
    
    def calculate_delta_hedge(
        self,
        underlying_symbol: str,
        current_delta: Decimal,
        underlying_price: Optional[Decimal] = None,
        target_delta: Decimal = Decimal("0")
    ) -> Optional[HedgeRecommendation]:
        """
        Calculate delta hedge for a given underlying.
        
        Args:
            underlying_symbol: The underlying to hedge (MSFT, SPY, /GC)
            current_delta: Current delta exposure (signed)
            underlying_price: Current price of underlying
            target_delta: Target delta after hedge (default: 0 = fully hedged)
        
        Returns:
            HedgeRecommendation or None if no hedge needed
        """
        delta_to_hedge = target_delta - current_delta
        
        # If delta to hedge is negligible, no action needed
        if abs(delta_to_hedge) < Decimal("0.5"):
            return None
        
        # Determine hedge type based on underlying
        is_futures = underlying_symbol.startswith("/")
        
        if is_futures:
            # Hedge with futures contracts
            # For futures, delta is usually quoted per contract
            # Quantity = delta to hedge (rounded to whole contracts)
            quantity = int(round(delta_to_hedge))
            if quantity == 0:
                return None
                
            return HedgeRecommendation(
                underlying_symbol=underlying_symbol,
                hedge_type=HedgeType.FUTURES,
                quantity=quantity,  # Positive = buy, Negative = sell
                instrument_symbol=underlying_symbol,
                current_price=underlying_price,
                target_greek="delta",
                current_exposure=current_delta,
                post_hedge_exposure=current_delta + Decimal(quantity),
                estimated_cost=abs(Decimal(quantity)) * (underlying_price or Decimal("0")) if underlying_price else None
            )
        else:
            # Hedge with stock shares
            # For equity options, delta 1.0 = 100 shares (due to multiplier)
            # So to hedge delta of -1.5, need to buy 150 shares
            shares_needed = int(round(delta_to_hedge * 100))
            if shares_needed == 0:
                return None
            
            estimated_cost = None
            if underlying_price:
                estimated_cost = abs(shares_needed) * underlying_price
            
            return HedgeRecommendation(
                underlying_symbol=underlying_symbol,
                hedge_type=HedgeType.SHARES,
                quantity=shares_needed,  # Positive = buy, Negative = sell
                instrument_symbol=underlying_symbol,
                current_price=underlying_price,
                target_greek="delta",
                current_exposure=current_delta,
                post_hedge_exposure=current_delta + Decimal(shares_needed) / 100,
                estimated_cost=estimated_cost
            )
    
    def calculate_portfolio_hedge(
        self,
        risk_buckets: Dict[str, RiskBucket]
    ) -> List[HedgeRecommendation]:
        """
        Calculate hedges for entire portfolio.
        
        Args:
            risk_buckets: Dict of underlying -> RiskBucket
        
        Returns:
            List of hedge recommendations (one per underlying with exposure)
        """
        recommendations = []
        
        for underlying, bucket in risk_buckets.items():
            # Get underlying price from registry if available
            underlying_price = self._get_underlying_price(underlying)
            
            # Calculate delta hedge
            hedge = self.calculate_delta_hedge(
                underlying_symbol=underlying,
                current_delta=bucket.delta,
                underlying_price=underlying_price
            )
            
            if hedge:
                recommendations.append(hedge)
        
        return recommendations
    
    def _get_underlying_price(self, underlying_symbol: str) -> Optional[Decimal]:
        """Get underlying price from registry."""
        # Look for the underlying as a registered instrument
        instrument = self.registry.get_by_id(underlying_symbol)
        if instrument and instrument.current_price:
            return instrument.current_price
        
        # Look for any instrument with this underlying and get the underlying factor
        for inst in self.registry.instruments.values():
            if inst.underlying_symbol == underlying_symbol:
                underlying_factor = inst.get_underlying_factor()
                if underlying_factor and underlying_factor.mark:
                    return underlying_factor.mark
        
        return None
    
    def aggregate_risk_by_underlying(
        self,
        positions: List[dict]  # List of {instrument_id, quantity, greeks}
    ) -> Dict[str, RiskBucket]:
        """
        Aggregate position greeks into risk buckets by underlying.
        
        Args:
            positions: List of position dicts with instrument_id, quantity, greeks
        
        Returns:
            Dict mapping underlying symbol to RiskBucket
        """
        buckets: Dict[str, RiskBucket] = {}
        
        for pos in positions:
            instrument_id = pos.get("instrument_id")
            quantity = pos.get("quantity", 0)
            greeks = pos.get("greeks")
            
            if not instrument_id or not greeks:
                continue
            
            # Find instrument in registry
            instrument = self.registry.get_by_id(instrument_id)
            if not instrument:
                continue
            
            # Determine the underlying
            underlying = instrument.underlying_symbol or instrument.ticker
            
            # Create bucket if needed
            if underlying not in buckets:
                buckets[underlying] = RiskBucket(underlying=underlying)
            
            # Add greeks to bucket
            expiry_str = instrument.expiry.isoformat() if instrument.expiry else None
            buckets[underlying].add_position_greeks(greeks, expiry_str, quantity)
        
        return buckets


# =============================================================================
# Example usage
# =============================================================================

if __name__ == "__main__":
    from decimal import Decimal
    from datetime import date
    from market_data import (
        InstrumentRegistry, create_stock_instrument, create_equity_option_instrument,
        OptionType, Greeks
    )
    
    # Setup
    registry = InstrumentRegistry()
    
    # Register instruments
    spy_stock = create_stock_instrument("SPY")
    registry.register(spy_stock)
    
    spy_put = create_equity_option_instrument(
        occ_symbol="SPY   260131P00580000",
        ticker="SPY",
        option_type=OptionType.PUT,
        strike=Decimal("580"),
        expiry=date(2026, 1, 31)
    )
    registry.register(spy_put)
    
    # Simulate market data on the underlying
    spy_stock_factor = spy_stock.get_self_factor()
    if spy_stock_factor:
        spy_stock_factor.update_market_data(
            bid=Decimal("588.20"),
            ask=Decimal("588.30"),
            mark=Decimal("588.25")
        )
    
    # Create hedge calculator
    calc = HedgeCalculator(registry)
    
    # Example 1: Calculate delta hedge
    print("=== Delta Hedge Example ===")
    hedge = calc.calculate_delta_hedge(
        underlying_symbol="SPY",
        current_delta=Decimal("-1.50"),  # Short 150 delta
        underlying_price=Decimal("588.25")
    )
    
    if hedge:
        print(f"Recommendation: {hedge.action} {abs(hedge.quantity)} {hedge.instrument_symbol}")
        print(f"  Current delta: {hedge.current_exposure}")
        print(f"  Post-hedge delta: {hedge.post_hedge_exposure}")
        print(f"  Estimated cost: ${hedge.estimated_cost:,.2f}")
    
    # Example 2: Risk bucket aggregation
    print("\n=== Risk Bucket Example ===")
    
    positions = [
        {
            "instrument_id": "SPY   260131P00580000",
            "quantity": -2,
            "greeks": Greeks(
                delta=Decimal("-0.40"),
                gamma=Decimal("0.02"),
                theta=Decimal("0.15"),
                vega=Decimal("0.30")
            )
        },
        {
            "instrument_id": "SPY   260131P00580000",
            "quantity": -3,
            "greeks": Greeks(
                delta=Decimal("-0.40"),
                gamma=Decimal("0.02"),
                theta=Decimal("0.15"),
                vega=Decimal("0.30")
            )
        }
    ]
    
    buckets = calc.aggregate_risk_by_underlying(positions)
    
    for underlying, bucket in buckets.items():
        print(f"\n{underlying} Risk Bucket:")
        print(f"  Delta: {bucket.delta}")
        print(f"  Gamma: {bucket.gamma}")
        print(f"  Theta: {bucket.theta}")
        print(f"  Vega: {bucket.vega}")
        print(f"  Positions: {bucket.position_count}")
        
        # Calculate dollar exposures
        bucket.calculate_dollar_exposures(Decimal("588.25"))
        print(f"  Delta $: ${bucket.delta_dollars:,.2f}")
