"""
Functional Calculation Layer - Pure Functions for Domain Models

KEY INSIGHT: Separate DATA (domain.py) from CALCULATIONS (this file)

Benefits:
1. Test any scenario without mutating data
2. Two-source pattern for everything (broker vs calculated)
3. Compose complex analyses from pure functions
4. Foundation for ML (reproducible calculations)

Architecture:
- domain.py: Data structures (Leg, Position, etc.) - IMMUTABLE
- calculations.py: Pure functions - NO SIDE EFFECTS
"""

from dataclasses import dataclass
from typing import Optional, Literal
from decimal import Decimal
from datetime import datetime
import trading_cotrader.core.models.domain as dm


# ============================================================================
# PART 1: Market State (Input to all calculations)
# ============================================================================

@dataclass(frozen=True)
class MarketState:
    """
    Complete market state for calculations
    
    This is the INPUT to all pricing/Greeks functions
    """
    # Current market data
    spot_price: Decimal
    timestamp: datetime
    
    # Volatility (from surface or single value)
    volatility: Optional[Decimal] = None  # Single IV
    volatility_surface: Optional['VolatilitySurface'] = None  # Full surface
    
    # Risk-free rate and dividends
    risk_free_rate: Decimal = Decimal('0.053')
    dividend_yield: Decimal = Decimal('0.015')
    
    # Scenario adjustments (for what-if analysis)
    spot_price_adjustment: Decimal = Decimal('0')  # Add to spot
    volatility_adjustment: Decimal = Decimal('0')  # Add to IV
    days_forward: int = 0  # Time decay simulation
    
    def get_adjusted_spot(self) -> Decimal:
        """Spot price with scenario adjustment"""
        return self.spot_price + self.spot_price_adjustment
    
    def get_adjusted_volatility(self, base_iv: Decimal) -> Decimal:
        """Volatility with scenario adjustment"""
        return base_iv + self.volatility_adjustment
    
    @classmethod
    def current(cls, spot_price: Decimal, **kwargs) -> 'MarketState':
        """Create current market state (no adjustments)"""
        return cls(
            spot_price=spot_price,
            timestamp=datetime.utcnow(),
            **kwargs
        )
    
    @classmethod
    def scenario(
        cls,
        spot_price: Decimal,
        spot_change_pct: float = 0,
        iv_change: float = 0,
        days_forward: int = 0,
        **kwargs
    ) -> 'MarketState':
        """Create scenario market state"""
        spot_adjustment = spot_price * Decimal(str(spot_change_pct / 100))
        
        return cls(
            spot_price=spot_price,
            timestamp=datetime.utcnow(),
            spot_price_adjustment=spot_adjustment,
            volatility_adjustment=Decimal(str(iv_change)),
            days_forward=days_forward,
            **kwargs
        )


# ============================================================================
# PART 2: Pricing Sources
# ============================================================================

PriceSource = Literal['broker', 'calculated', 'mid']


def calculate_option_price(
    leg: dm.Leg,
    market_state: MarketState,
    source: PriceSource = 'calculated',
    greeks_engine: Optional['GreeksEngine'] = None
) -> Decimal:
    """
    Calculate option price from any source
    
    Args:
        leg: Leg to price
        market_state: Market conditions
        source: 'broker' (use leg.current_price), 'calculated' (Black-Scholes), 'mid' (bid-ask mid)
        greeks_engine: Engine for calculations (required if source='calculated')
    
    Returns:
        Option price
    
    Usage:
        # Current broker price
        price = calculate_option_price(leg, market_state, source='broker')
        
        # Calculated price with scenario
        scenario_state = MarketState.scenario(spot_price=210, spot_change_pct=-5)
        price = calculate_option_price(leg, scenario_state, source='calculated', greeks_engine=engine)
    """
    
    if source == 'broker':
        # Use frozen broker price
        if leg.current_price is None:
            raise ValueError("No broker price available")
        return leg.current_price
    
    elif source == 'mid':
        # Calculate mid from bid-ask (if available)
        # Would need bid/ask in Leg model
        raise NotImplementedError("Bid-ask mid not yet implemented")
    
    elif source == 'calculated':
        # Calculate using Black-Scholes
        if leg.symbol.asset_type != dm.AssetType.OPTION:
            # For equity, price = spot
            return market_state.get_adjusted_spot()
        
        if greeks_engine is None:
            raise ValueError("greeks_engine required for calculated pricing")
        
        # Get volatility
        if market_state.volatility_surface:
            iv = market_state.volatility_surface.get_iv(
                leg.symbol.strike,
                leg.symbol.expiration.date()
            )
        elif market_state.volatility:
            iv = market_state.volatility
        else:
            raise ValueError("No volatility data in market state")
        
        # Adjust for scenario
        iv = market_state.get_adjusted_volatility(iv)
        
        # Calculate time to expiry
        time_to_expiry = (leg.symbol.expiration - market_state.timestamp).total_seconds() / (365.25 * 24 * 3600)
        time_to_expiry -= market_state.days_forward / 365.25
        
        if time_to_expiry <= 0:
            # Expired - calculate intrinsic value
            spot = market_state.get_adjusted_spot()
            if leg.symbol.option_type == dm.OptionType.CALL:
                intrinsic = max(Decimal('0'), spot - leg.symbol.strike)
            else:
                intrinsic = max(Decimal('0'), leg.symbol.strike - spot)
            return intrinsic
        
        # Calculate price
        price = greeks_engine.calculate_option_price(
            option_type=leg.symbol.option_type.value,
            spot_price=float(market_state.get_adjusted_spot()),
            strike=float(leg.symbol.strike),
            time_to_expiry=time_to_expiry,
            volatility=float(iv),
            risk_free_rate=float(market_state.risk_free_rate),
            dividend_yield=float(market_state.dividend_yield)
        )
        
        return Decimal(str(price))
    
    else:
        raise ValueError(f"Unknown price source: {source}")


def calculate_leg_pnl(
    leg: dm.Leg,
    market_state: MarketState,
    price_source: PriceSource = 'broker',
    greeks_engine: Optional['GreeksEngine'] = None
) -> Decimal:
    """
    Calculate P&L for a leg
    
    Usage:
        # Current P&L (broker prices)
        pnl = calculate_leg_pnl(leg, market_state, source='broker')
        
        # Scenario P&L (calculated prices)
        scenario = MarketState.scenario(spot_price=210, spot_change_pct=-5)
        pnl = calculate_leg_pnl(leg, scenario, source='calculated', greeks_engine=engine)
    """
    
    if not leg.entry_price:
        return Decimal('0')
    
    # Get current price
    current_price = calculate_option_price(leg, market_state, price_source, greeks_engine)
    
    # Calculate P&L
    pnl = (current_price - leg.entry_price) * leg.quantity * leg.symbol.multiplier
    
    # Subtract costs
    pnl -= (leg.fees + leg.commission)
    
    return pnl


# ============================================================================
# PART 3: Position-Level Calculations
# ============================================================================

def calculate_position_pnl(
    position: dm.Position,
    market_state: MarketState,
    price_source: PriceSource = 'broker',
    greeks_engine: Optional['GreeksEngine'] = None
) -> Decimal:
    """
    Calculate position P&L
    
    For positions (not trades), we use simple price difference
    """
    
    if not position.average_price:
        return Decimal('0')
    
    # Get current price based on source
    if price_source == 'broker':
        current_price = position.current_price or Decimal('0')
    else:
        # Would need to create a Leg from Position for pricing
        # Simplified: use broker price for now
        current_price = position.current_price or Decimal('0')
    
    # Calculate P&L
    pnl = (current_price - position.average_price) * position.quantity * position.symbol.multiplier
    
    return pnl


def calculate_position_greeks(
    position: dm.Position,
    market_state: MarketState,
    source: Literal['broker', 'calculated'] = 'broker',
    greeks_engine: Optional['GreeksEngine'] = None
) -> Optional[dm.Greeks]:
    """
    Calculate Greeks for a position
    
    Usage:
        # Broker Greeks (from position.greeks)
        greeks = calculate_position_greeks(position, market_state, source='broker')
        
        # Calculated Greeks (from volatility surface)
        greeks = calculate_position_greeks(
            position, 
            market_state, 
            source='calculated',
            greeks_engine=engine
        )
    """
    
    if source == 'broker':
        # Return stored broker Greeks
        return position.greeks
    
    elif source == 'calculated':
        # Calculate Greeks from market state
        if position.symbol.asset_type != dm.AssetType.OPTION:
            # Equity: delta = quantity, others = 0
            return dm.Greeks(
                delta=Decimal(str(position.quantity)),
                gamma=Decimal('0'),
                theta=Decimal('0'),
                vega=Decimal('0'),
                rho=Decimal('0'),
                timestamp=datetime.utcnow()
            )
        
        if greeks_engine is None:
            raise ValueError("greeks_engine required for calculated Greeks")
        
        # Get volatility
        if market_state.volatility_surface:
            iv = market_state.volatility_surface.get_iv(
                position.symbol.strike,
                position.symbol.expiration.date()
            )
        elif market_state.volatility:
            iv = market_state.volatility
        else:
            raise ValueError("No volatility data in market state")
        
        # Calculate time to expiry
        time_to_expiry = (position.symbol.expiration - market_state.timestamp).total_seconds() / (365.25 * 24 * 3600)
        time_to_expiry -= market_state.days_forward / 365.25
        
        if time_to_expiry <= 0:
            # Expired
            return dm.Greeks(
                delta=Decimal('0'), gamma=Decimal('0'), theta=Decimal('0'),
                vega=Decimal('0'), rho=Decimal('0'), timestamp=datetime.utcnow()
            )
        
        # Calculate Greeks
        greeks_calc = greeks_engine.calculate_greeks(
            option_type=position.symbol.option_type.value,
            spot_price=float(market_state.get_adjusted_spot()),
            strike=float(position.symbol.strike),
            time_to_expiry=time_to_expiry,
            volatility=float(iv),
            risk_free_rate=float(market_state.risk_free_rate),
            dividend_yield=float(market_state.dividend_yield)
        )
        
        # Position-level Greeks (multiply by quantity)
        return dm.Greeks(
            delta=greeks_calc.delta * abs(position.quantity),
            gamma=greeks_calc.gamma * abs(position.quantity),
            theta=greeks_calc.theta * abs(position.quantity),
            vega=greeks_calc.vega * abs(position.quantity),
            rho=greeks_calc.rho * abs(position.quantity),
            timestamp=datetime.utcnow()
        )
    
    else:
        raise ValueError(f"Unknown Greeks source: {source}")


# ============================================================================
# PART 4: Portfolio-Level Calculations
# ============================================================================

def calculate_portfolio_greeks(
    positions: list[dm.Position],
    market_state: MarketState,
    source: Literal['broker', 'calculated'] = 'broker',
    greeks_engine: Optional['GreeksEngine'] = None
) -> dm.Greeks:
    """
    Aggregate Greeks across portfolio
    
    Usage:
        # Broker Greeks (operational truth)
        greeks = calculate_portfolio_greeks(positions, market_state, source='broker')
        
        # Calculated Greeks (arbitrage detection)
        greeks = calculate_portfolio_greeks(
            positions, 
            market_state, 
            source='calculated',
            greeks_engine=engine
        )
    """
    
    total_delta = Decimal('0')
    total_gamma = Decimal('0')
    total_theta = Decimal('0')
    total_vega = Decimal('0')
    total_rho = Decimal('0')
    
    for position in positions:
        greeks = calculate_position_greeks(position, market_state, source, greeks_engine)
        
        if greeks:
            total_delta += greeks.delta
            total_gamma += greeks.gamma
            total_theta += greeks.theta
            total_vega += greeks.vega
            total_rho += greeks.rho
    
    return dm.Greeks(
        delta=total_delta,
        gamma=total_gamma,
        theta=total_theta,
        vega=total_vega,
        rho=total_rho,
        timestamp=datetime.utcnow()
    )


def calculate_portfolio_pnl(
    positions: list[dm.Position],
    market_state: MarketState,
    price_source: PriceSource = 'broker',
    greeks_engine: Optional['GreeksEngine'] = None
) -> Decimal:
    """Calculate total portfolio P&L"""
    
    total_pnl = Decimal('0')
    
    for position in positions:
        pnl = calculate_position_pnl(position, market_state, price_source, greeks_engine)
        total_pnl += pnl
    
    return total_pnl


# ============================================================================
# PART 5: Example Usage
# ============================================================================

"""
EXAMPLE 1: Compare Broker vs Calculated Greeks
-----------------------------------------------
from core.models.calculations import (
    MarketState, calculate_portfolio_greeks
)
from analytics.greeks.engine import GreeksEngine

# Current market state
market_state = MarketState.current(
    spot_price=Decimal('209.50'),
    volatility_surface=surface
)

# Broker Greeks (operational)
broker_greeks = calculate_portfolio_greeks(
    positions, market_state, source='broker'
)

# Calculated Greeks (arbitrage detection)
engine = GreeksEngine()
calc_greeks = calculate_portfolio_greeks(
    positions, market_state, source='calculated', greeks_engine=engine
)

# Compare
delta_diff = abs(broker_greeks.delta - calc_greeks.delta)
if delta_diff > 10:
    print(f"⚠️ DELTA MISMATCH: {delta_diff:.2f}")


EXAMPLE 2: Scenario Testing
----------------------------
# What if SPY drops 5%?
crash_scenario = MarketState.scenario(
    spot_price=Decimal('209.50'),
    spot_change_pct=-5.0,
    iv_change=0.10,  # IV spikes 10%
    volatility_surface=surface
)

crash_greeks = calculate_portfolio_greeks(
    positions, crash_scenario, source='calculated', greeks_engine=engine
)

crash_pnl = calculate_portfolio_pnl(
    positions, crash_scenario, price_source='calculated', greeks_engine=engine
)

print(f"After 5% crash:")
print(f"  Delta: {crash_greeks.delta:.2f}")
print(f"  P&L: ${crash_pnl:,.2f}")


EXAMPLE 3: Pre-Trade Analysis
------------------------------
# Test adding a new position
proposed_leg = dm.Leg(
    symbol=dm.Symbol(ticker='IWM', strike=210, ...),
    quantity=-2,
    entry_price=Decimal('3.50')
)

# Current portfolio
current_greeks = calculate_portfolio_greeks(positions, market_state, ...)

# Portfolio with new leg
new_positions = positions + [convert_leg_to_position(proposed_leg)]
new_greeks = calculate_portfolio_greeks(new_positions, market_state, ...)

# Impact
delta_impact = new_greeks.delta - current_greeks.delta
print(f"Adding leg changes delta by: {delta_impact:.2f}")
"""

if __name__ == "__main__":
    from trading_cotrader.core.models.calculations import MarketState
    from decimal import Decimal

    state = MarketState.current(Decimal('100'))
    print(f'✓ Market state: {state}')