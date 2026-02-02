"""
Implied Volatility Calculator

Calculate IV from market prices and analyze IV surface.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math
import logging

from services.pricing.black_scholes import BlackScholesModel, OptionType

logger = logging.getLogger(__name__)


@dataclass
class IVPoint:
    """Single point on IV surface"""
    strike: float
    expiration: datetime
    iv: float
    option_type: OptionType


@dataclass
class IVSurface:
    """Implied volatility surface for an underlying"""
    underlying: str
    spot: float
    points: List[IVPoint] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def get_atm_iv(self, expiration: datetime) -> Optional[float]:
        """Get ATM IV for a given expiration."""
        # Find points closest to ATM for this expiration
        exp_points = [p for p in self.points if p.expiration == expiration]
        if not exp_points:
            return None
        
        # Find closest to spot
        closest = min(exp_points, key=lambda p: abs(p.strike - self.spot))
        return closest.iv
    
    def get_iv(self, strike: float, expiration: datetime) -> Optional[float]:
        """Get IV for specific strike/expiration."""
        for p in self.points:
            if p.strike == strike and p.expiration == expiration:
                return p.iv
        return None


class ImpliedVolCalculator:
    """
    Calculate implied volatility from option prices.
    
    Usage:
        calc = ImpliedVolCalculator()
        
        # Get IV from market price
        iv = calc.calculate_iv(
            market_price=5.50,
            spot=100,
            strike=105,
            days_to_expiry=30,
            option_type='call'
        )
        
        # Build IV surface
        surface = calc.build_iv_surface(underlying='AAPL', option_chain=chain)
    """
    
    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6):
        self.bs_model = BlackScholesModel()
        self.max_iterations = max_iterations
        self.tolerance = tolerance
    
    def calculate_iv(
        self,
        market_price: float,
        spot: float,
        strike: float,
        days_to_expiry: int,
        option_type: str,  # 'call' or 'put'
        rate: float = 0.05
    ) -> Optional[float]:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Args:
            market_price: Current market price of option
            spot: Underlying price
            strike: Option strike
            days_to_expiry: Days until expiration
            option_type: 'call' or 'put'
            rate: Risk-free rate
            
        Returns:
            Implied volatility or None if doesn't converge
        """
        time_to_expiry = days_to_expiry / 365
        
        if time_to_expiry <= 0:
            return None
        
        opt_type = OptionType.CALL if option_type.lower() == 'call' else OptionType.PUT
        
        # Check for arbitrage violations
        if opt_type == OptionType.CALL:
            intrinsic = max(0, spot - strike)
        else:
            intrinsic = max(0, strike - spot)
        
        if market_price < intrinsic:
            logger.warning(f"Market price below intrinsic value")
            return None
        
        # Initial guess based on ATM approximation
        vol = math.sqrt(2 * abs(math.log(spot / strike)) / time_to_expiry) + 0.2
        vol = max(0.01, min(vol, 5.0))  # Bound initial guess
        
        for i in range(self.max_iterations):
            price = self.bs_model.price(spot, strike, time_to_expiry, rate, vol, opt_type)
            diff = price - market_price
            
            if abs(diff) < self.tolerance:
                return vol
            
            # Calculate vega for Newton-Raphson step
            greeks = self.bs_model.greeks(spot, strike, time_to_expiry, rate, vol, opt_type)
            vega = greeks.vega * 100  # Convert back to full vega
            
            if abs(vega) < 1e-10:
                # Vega too small, use bisection
                return self._bisection_iv(market_price, spot, strike, time_to_expiry, rate, opt_type)
            
            vol = vol - diff / vega
            vol = max(0.001, min(vol, 10.0))  # Keep vol in reasonable range
        
        logger.warning(f"IV calculation did not converge after {self.max_iterations} iterations")
        return self._bisection_iv(market_price, spot, strike, time_to_expiry, rate, opt_type)
    
    def _bisection_iv(
        self,
        market_price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        opt_type: OptionType
    ) -> Optional[float]:
        """Fallback bisection method for IV calculation."""
        low, high = 0.001, 5.0
        
        for _ in range(100):
            mid = (low + high) / 2
            price = self.bs_model.price(spot, strike, time_to_expiry, rate, mid, opt_type)
            
            if abs(price - market_price) < self.tolerance:
                return mid
            
            if price > market_price:
                high = mid
            else:
                low = mid
        
        return (low + high) / 2
    
    def calculate_iv_rank(
        self,
        current_iv: float,
        iv_52_week_low: float,
        iv_52_week_high: float
    ) -> float:
        """
        Calculate IV Rank.
        
        IV Rank = (Current IV - 52-week Low) / (52-week High - 52-week Low)
        
        Returns 0-100 value.
        """
        range_iv = iv_52_week_high - iv_52_week_low
        if range_iv <= 0:
            return 50.0
        
        rank = (current_iv - iv_52_week_low) / range_iv * 100
        return max(0, min(100, rank))
    
    def calculate_iv_percentile(
        self,
        current_iv: float,
        historical_ivs: List[float]
    ) -> float:
        """
        Calculate IV Percentile.
        
        IV Percentile = % of days in past year with lower IV than current
        
        Returns 0-100 value.
        """
        if not historical_ivs:
            return 50.0
        
        below = sum(1 for iv in historical_ivs if iv < current_iv)
        return below / len(historical_ivs) * 100
    
    def build_iv_surface(
        self,
        underlying: str,
        spot: float,
        option_chain: List[dict]
    ) -> IVSurface:
        """
        Build IV surface from option chain.
        
        Args:
            underlying: Ticker symbol
            spot: Current underlying price
            option_chain: List of option data with price, strike, expiration
            
        Returns:
            IVSurface object
        """
        surface = IVSurface(underlying=underlying, spot=spot)
        
        for option in option_chain:
            try:
                iv = self.calculate_iv(
                    market_price=option.get('mid_price', option.get('mark', 0)),
                    spot=spot,
                    strike=option['strike'],
                    days_to_expiry=option['days_to_expiry'],
                    option_type=option['option_type']
                )
                
                if iv:
                    opt_type = OptionType.CALL if option['option_type'].lower() == 'call' else OptionType.PUT
                    surface.points.append(IVPoint(
                        strike=option['strike'],
                        expiration=option['expiration'],
                        iv=iv,
                        option_type=opt_type
                    ))
            except Exception as e:
                logger.warning(f"Failed to calculate IV for option: {e}")
        
        return surface


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    calc = ImpliedVolCalculator()
    
    # Calculate IV from market price
    iv = calc.calculate_iv(
        market_price=5.00,
        spot=100,
        strike=105,
        days_to_expiry=30,
        option_type='call'
    )
    
    print(f"Implied Volatility: {iv*100:.2f}%")
    
    # IV Rank example
    rank = calc.calculate_iv_rank(
        current_iv=0.25,
        iv_52_week_low=0.15,
        iv_52_week_high=0.45
    )
    print(f"IV Rank: {rank:.1f}")
