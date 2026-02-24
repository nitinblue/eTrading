"""
Option Pricer - Black-Scholes pricing for options

Pure function: given inputs → price (no side effects)
"""

from decimal import Decimal
from typing import Literal
import numpy as np
from scipy.stats import norm


class OptionPricer:
    """Black-Scholes option pricing"""
    
    @staticmethod
    def price(
        option_type: Literal['call', 'put'],
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float = 0.053,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option price using Black-Scholes-Merton
        
        Args:
            option_type: 'call' or 'put'
            spot_price: Current underlying price
            strike: Strike price
            time_to_expiry: Time to expiration (years)
            volatility: Implied volatility (annualized)
            risk_free_rate: Risk-free rate (annualized)
            dividend_yield: Dividend yield (annualized)
        
        Returns:
            Option price per share
        """
        
        if time_to_expiry <= 0:
            # Expired - intrinsic value only
            if option_type == 'call':
                return max(0, spot_price - strike)
            else:
                return max(0, strike - spot_price)
        
        if volatility <= 0:
            raise ValueError("Volatility must be positive")
        
        # Calculate d1 and d2
        d1 = (np.log(spot_price / strike) + 
              (risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        # Calculate price
        if option_type == 'call':
            price = (spot_price * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1) -
                    strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2))
        else:  # put
            price = (strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) -
                    spot_price * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1))
        
        return max(0, price)
    
    @staticmethod
    def intrinsic_value(
        option_type: Literal['call', 'put'],
        spot_price: float,
        strike: float
    ) -> float:
        """Calculate intrinsic value (for expired options or quick checks)"""
        
        if option_type == 'call':
            return max(0, spot_price - strike)
        else:
            return max(0, strike - spot_price)


# Convenience function
def price_option(
    option_type: str,
    spot: float,
    strike: float,
    tte: float,
    vol: float,
    rate: float = 0.053,
    div: float = 0.0
) -> Decimal:
    """
    Convenience wrapper returning Decimal
    
    Usage:
        price = price_option('call', 210, 215, 0.08, 0.30)
    """
    price = OptionPricer.price(option_type, spot, strike, tte, vol, rate, div)
    return Decimal(str(price))


if __name__ == "__main__":
    # Example
    call_price = OptionPricer.price(
        option_type='call',
        spot_price=210,
        strike=215,
        time_to_expiry=0.08,  # ~30 days
        volatility=0.30,
        risk_free_rate=0.053,
        dividend_yield=0.015
    )
    
    print(f"Call price: ${call_price:.2f}")