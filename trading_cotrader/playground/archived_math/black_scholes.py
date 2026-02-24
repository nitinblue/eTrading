"""
Black-Scholes Model Implementation

The foundation of options pricing.
Provides price and Greeks calculations.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple
from enum import Enum
import math
import logging

logger = logging.getLogger(__name__)


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class BSGreeks:
    """Greeks from Black-Scholes model"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    
    # Per-contract values (multiply by 100 for options)
    delta_dollars: float = 0.0
    gamma_dollars: float = 0.0
    theta_daily: float = 0.0
    vega_dollars: float = 0.0


@dataclass
class OptionPrice:
    """Option pricing result"""
    price: float
    intrinsic_value: float
    time_value: float
    greeks: BSGreeks


class BlackScholesModel:
    """
    Black-Scholes-Merton option pricing model.
    
    Usage:
        bs = BlackScholesModel()
        
        # Price a call option
        price = bs.price(
            spot=100,
            strike=105,
            time_to_expiry=0.25,  # 3 months in years
            rate=0.05,           # 5% risk-free rate
            volatility=0.20,     # 20% annualized vol
            option_type=OptionType.CALL
        )
        
        # Get all Greeks
        greeks = bs.greeks(...)
    """
    
    def __init__(self, dividend_yield: float = 0.0):
        """
        Initialize model.
        
        Args:
            dividend_yield: Continuous dividend yield (default 0)
        """
        self.dividend_yield = dividend_yield
    
    def price(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: OptionType
    ) -> float:
        """
        Calculate option price using Black-Scholes formula.
        
        Args:
            spot: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            rate: Risk-free interest rate (annualized)
            volatility: Implied volatility (annualized)
            option_type: CALL or PUT
            
        Returns:
            Option price
        """
        if time_to_expiry <= 0:
            # At expiration, return intrinsic value
            if option_type == OptionType.CALL:
                return max(0, spot - strike)
            else:
                return max(0, strike - spot)
        
        d1, d2 = self._calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility)
        
        if option_type == OptionType.CALL:
            price = (
                spot * math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(d1) -
                strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(d2)
            )
        else:
            price = (
                strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(-d2) -
                spot * math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(-d1)
            )
        
        return max(0, price)
    
    def price_full(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: OptionType
    ) -> OptionPrice:
        """
        Calculate option price with full breakdown.
        
        Returns:
            OptionPrice with price, intrinsic, time value, and Greeks
        """
        price = self.price(spot, strike, time_to_expiry, rate, volatility, option_type)
        greeks = self.greeks(spot, strike, time_to_expiry, rate, volatility, option_type)
        
        # Calculate intrinsic and time value
        if option_type == OptionType.CALL:
            intrinsic = max(0, spot - strike)
        else:
            intrinsic = max(0, strike - spot)
        
        time_value = price - intrinsic
        
        return OptionPrice(
            price=price,
            intrinsic_value=intrinsic,
            time_value=time_value,
            greeks=greeks
        )
    
    def greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: OptionType
    ) -> BSGreeks:
        """
        Calculate all Greeks for an option.
        
        Returns:
            BSGreeks object with all Greek values
        """
        if time_to_expiry <= 0:
            # At expiration
            delta = 1.0 if (option_type == OptionType.CALL and spot > strike) else 0.0
            if option_type == OptionType.PUT:
                delta = -1.0 if spot < strike else 0.0
            return BSGreeks(delta=delta)
        
        d1, d2 = self._calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility)
        sqrt_t = math.sqrt(time_to_expiry)
        
        # Delta
        if option_type == OptionType.CALL:
            delta = math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(d1)
        else:
            delta = -math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(-d1)
        
        # Gamma (same for calls and puts)
        gamma = (
            math.exp(-self.dividend_yield * time_to_expiry) * 
            self._norm_pdf(d1) / (spot * volatility * sqrt_t)
        )
        
        # Theta (per year, divide by 365 for daily)
        theta_term1 = -(spot * volatility * math.exp(-self.dividend_yield * time_to_expiry) * 
                        self._norm_pdf(d1)) / (2 * sqrt_t)
        
        if option_type == OptionType.CALL:
            theta = (
                theta_term1 -
                rate * strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(d2) +
                self.dividend_yield * spot * math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(d1)
            )
        else:
            theta = (
                theta_term1 +
                rate * strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(-d2) -
                self.dividend_yield * spot * math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(-d1)
            )
        
        # Vega (same for calls and puts) - per 1% move in vol
        vega = spot * math.exp(-self.dividend_yield * time_to_expiry) * sqrt_t * self._norm_pdf(d1) / 100
        
        # Rho (per 1% move in rate)
        if option_type == OptionType.CALL:
            rho = strike * time_to_expiry * math.exp(-rate * time_to_expiry) * self._norm_cdf(d2) / 100
        else:
            rho = -strike * time_to_expiry * math.exp(-rate * time_to_expiry) * self._norm_cdf(-d2) / 100
        
        return BSGreeks(
            delta=delta,
            gamma=gamma,
            theta=theta / 365,  # Convert to daily
            vega=vega,
            rho=rho,
            delta_dollars=delta * spot,
            gamma_dollars=gamma * spot * spot / 100,
            theta_daily=theta / 365,
            vega_dollars=vega
        )
    
    def delta(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: OptionType
    ) -> float:
        """Calculate just delta (faster than full Greeks)."""
        if time_to_expiry <= 0:
            if option_type == OptionType.CALL:
                return 1.0 if spot > strike else 0.0
            else:
                return -1.0 if spot < strike else 0.0
        
        d1, _ = self._calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility)
        
        if option_type == OptionType.CALL:
            return math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(d1)
        else:
            return -math.exp(-self.dividend_yield * time_to_expiry) * self._norm_cdf(-d1)
    
    def _calculate_d1_d2(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float
    ) -> Tuple[float, float]:
        """Calculate d1 and d2 for Black-Scholes formula."""
        sqrt_t = math.sqrt(time_to_expiry)
        
        d1 = (
            math.log(spot / strike) + 
            (rate - self.dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * sqrt_t)
        
        d2 = d1 - volatility * sqrt_t
        
        return d1, d2
    
    def _norm_cdf(self, x: float) -> float:
        """Cumulative distribution function for standard normal."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    def _norm_pdf(self, x: float) -> float:
        """Probability density function for standard normal."""
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    bs = BlackScholesModel()
    
    # Example: AAPL call option
    # Spot: $150, Strike: $155, 30 days to expiry, 5% rate, 25% vol
    
    spot = 150
    strike = 155
    tte = 30 / 365  # 30 days in years
    rate = 0.05
    vol = 0.25
    
    call_price = bs.price(spot, strike, tte, rate, vol, OptionType.CALL)
    put_price = bs.price(spot, strike, tte, rate, vol, OptionType.PUT)
    
    print(f"Call Price: ${call_price:.2f}")
    print(f"Put Price: ${put_price:.2f}")
    
    # Verify put-call parity
    parity_diff = call_price - put_price - (spot - strike * math.exp(-rate * tte))
    print(f"Put-Call Parity Error: ${parity_diff:.6f}")
    
    # Greeks
    greeks = bs.greeks(spot, strike, tte, rate, vol, OptionType.CALL)
    print(f"\nCall Greeks:")
    print(f"  Delta: {greeks.delta:.4f}")
    print(f"  Gamma: {greeks.gamma:.6f}")
    print(f"  Theta: ${greeks.theta_daily:.4f}/day")
    print(f"  Vega:  ${greeks.vega:.4f}/1% vol")
