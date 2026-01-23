"""
P&L Calculator - Pure functions for calculating profit/loss

Supports:
- Leg-level P&L
- Position-level P&L  
- Trade-level P&L
- Portfolio-level P&L
- P&L attribution (by Greek)
"""

from decimal import Decimal
from typing import List, Dict, Literal
import trading_cotrader.core.models.domain as dm


# ============================================================================
# Leg P&L
# ============================================================================

def calculate_leg_pnl(
    leg: dm.Leg,
    current_price: Decimal,
    include_costs: bool = True
) -> Decimal:
    """
    Calculate P&L for a single leg
    
    Args:
        leg: Leg to calculate P&L for
        current_price: Current market price
        include_costs: Include fees and commissions
    
    Returns:
        P&L in dollars
    """
    
    if not leg.entry_price:
        return Decimal('0')
    
    # Price difference
    price_diff = current_price - leg.entry_price
    
    # P&L = price_diff × quantity × multiplier
    pnl = price_diff * leg.quantity * leg.symbol.multiplier
    
    # Subtract costs
    if include_costs:
        pnl -= (leg.fees + leg.commission)
    
    return pnl


def calculate_leg_pnl_percent(leg: dm.Leg, current_price: Decimal) -> Decimal:
    """Calculate P&L as percentage of entry cost"""
    
    if not leg.entry_price or leg.entry_price == 0:
        return Decimal('0')
    
    entry_cost = abs(leg.entry_price * leg.quantity * leg.symbol.multiplier)
    if entry_cost == 0:
        return Decimal('0')
    
    pnl_dollars = calculate_leg_pnl(leg, current_price, include_costs=False)
    
    return (pnl_dollars / entry_cost) * 100


# ============================================================================
# Position P&L
# ============================================================================

def calculate_position_pnl(
    position: dm.Position,
    current_price: Decimal = None
) -> Decimal:
    """
    Calculate position P&L
    
    Args:
        position: Position to calculate
        current_price: Override current price (for scenarios)
    
    Returns:
        Unrealized P&L in dollars
    """
    
    price = current_price if current_price is not None else position.current_price
    
    if not price or not position.average_price:
        return Decimal('0')
    
    price_diff = price - position.average_price
    pnl = price_diff * position.quantity * position.symbol.multiplier
    
    return pnl


def calculate_position_pnl_percent(position: dm.Position) -> Decimal:
    """Calculate position P&L as percentage"""
    
    if not position.total_cost or position.total_cost == 0:
        return Decimal('0')
    
    pnl = calculate_position_pnl(position)
    return (pnl / abs(position.total_cost)) * 100


# ============================================================================
# Trade P&L
# ============================================================================

def calculate_trade_pnl(trade: dm.Trade) -> Decimal:
    """
    Calculate total trade P&L (all legs)
    
    Returns:
        Total unrealized or realized P&L
    """
    
    total_pnl = Decimal('0')
    
    for leg in trade.legs:
        if leg.is_open():
            # Unrealized
            pnl = calculate_leg_pnl(leg, leg.current_price or Decimal('0'))
        else:
            # Realized
            if leg.exit_price:
                pnl = calculate_leg_pnl(leg, leg.exit_price)
            else:
                pnl = Decimal('0')
        
        total_pnl += pnl
    
    return total_pnl


# ============================================================================
# Portfolio P&L
# ============================================================================

def calculate_portfolio_pnl(
    positions: List[dm.Position],
    scenario_prices: Dict[str, Decimal] = None
) -> Decimal:
    """
    Calculate total portfolio P&L
    
    Args:
        positions: List of positions
        scenario_prices: Optional dict of {symbol: price} for scenarios
    
    Returns:
        Total unrealized P&L
    """
    
    total_pnl = Decimal('0')
    
    for position in positions:
        # Get price (scenario or current)
        if scenario_prices and position.symbol.ticker in scenario_prices:
            price = scenario_prices[position.symbol.ticker]
        else:
            price = position.current_price
        
        pnl = calculate_position_pnl(position, price)
        total_pnl += pnl
    
    return total_pnl


# ============================================================================
# P&L Attribution (by Greek)
# ============================================================================

def calculate_pnl_attribution(
    position: dm.Position,
    price_change: Decimal,
    vol_change: Decimal = Decimal('0'),
    time_decay_days: int = 0
) -> Dict[str, Decimal]:
    """
    Attribute P&L to Greeks
    
    Returns:
        {
            'delta': P&L from price move,
            'gamma': P&L from gamma (second order),
            'theta': P&L from time decay,
            'vega': P&L from volatility change,
            'total': Total attributed P&L
        }
    """
    
    if not position.greeks:
        return {
            'delta': Decimal('0'),
            'gamma': Decimal('0'),
            'theta': Decimal('0'),
            'vega': Decimal('0'),
            'total': Decimal('0')
        }
    
    greeks = position.greeks
    multiplier = position.symbol.multiplier
    
    # Delta P&L (first order)
    pnl_delta = greeks.delta * price_change * multiplier
    
    # Gamma P&L (second order)
    pnl_gamma = Decimal('0.5') * greeks.gamma * (price_change ** 2) * multiplier
    
    # Theta P&L
    pnl_theta = greeks.theta * time_decay_days * multiplier
    
    # Vega P&L (vega is per 1% IV change)
    pnl_vega = greeks.vega * vol_change * 100 * multiplier
    
    total = pnl_delta + pnl_gamma + pnl_theta + pnl_vega
    
    return {
        'delta': pnl_delta,
        'gamma': pnl_gamma,
        'theta': pnl_theta,
        'vega': pnl_vega,
        'total': total
    }


def calculate_portfolio_pnl_attribution(
    positions: List[dm.Position],
    price_changes: Dict[str, Decimal],
    vol_change: Decimal = Decimal('0'),
    time_decay_days: int = 0
) -> Dict[str, Decimal]:
    """
    Attribute portfolio P&L to Greeks
    
    Args:
        positions: List of positions
        price_changes: Dict of {symbol: price_change}
        vol_change: Overall volatility change
        time_decay_days: Days forward
    
    Returns:
        Aggregated P&L attribution
    """
    
    total_delta = Decimal('0')
    total_gamma = Decimal('0')
    total_theta = Decimal('0')
    total_vega = Decimal('0')
    
    for position in positions:
        price_change = price_changes.get(position.symbol.ticker, Decimal('0'))
        
        attribution = calculate_pnl_attribution(
            position, price_change, vol_change, time_decay_days
        )
        
        total_delta += attribution['delta']
        total_gamma += attribution['gamma']
        total_theta += attribution['theta']
        total_vega += attribution['vega']
    
    total = total_delta + total_gamma + total_theta + total_vega
    
    return {
        'delta': total_delta,
        'gamma': total_gamma,
        'theta': total_theta,
        'vega': total_vega,
        'total': total
    }


# ============================================================================
# Quick helpers
# ============================================================================

def pnl(entry: float, current: float, quantity: int, multiplier: int = 1) -> Decimal:
    """Quick P&L calculation"""
    return Decimal(str((current - entry) * quantity * multiplier))


if __name__ == "__main__":
    # Example
    print("Quick P&L calculation:")
    print(f"  Entry: $3.50, Current: $4.20, Qty: -2")
    print(f"  P&L: ${pnl(3.50, 4.20, -2, 100)}")