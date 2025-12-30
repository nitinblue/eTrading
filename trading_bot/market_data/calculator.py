# trading_bot/market_data/calculator.py
from scipy.stats import norm
from math import log, sqrt, exp
from typing import Dict

class BlackScholesCalculator:
    @staticmethod
    def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> Dict:
        """Calculate Greeks using Black-Scholes."""
        if T <= 0:
            return {'delta': 1.0 if option_type == 'call' else -1.0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0}
        d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        if option_type == 'call':
            delta = norm.cdf(d1)
            gamma = norm.pdf(d1) / (S * sigma * sqrt(T))
            vega = S * norm.pdf(d1) * sqrt(T)
            theta = - (S * norm.pdf(d1) * sigma) / (2 * sqrt(T)) - r * K * exp(-r * T) * norm.cdf(d2)
            rho = K * T * exp(-r * T) * norm.cdf(d2)
        else:
            delta = norm.cdf(d1) - 1
            gamma = norm.pdf(d1) / (S * sigma * sqrt(T))
            vega = S * norm.pdf(d1) * sqrt(T)
            theta = - (S * norm.pdf(d1) * sigma) / (2 * sqrt(T)) + r * K * exp(-r * T) * norm.cdf(-d2)
            rho = -K * T * exp(-r * T) * norm.cdf(-d2)
        return {
            'delta': delta,
            'gamma': gamma,
            'vega': vega / 100,
            'theta': theta / 365,
            'rho': rho / 100
        }

    @staticmethod
    def calculate_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> float:
        if T <= 0:
            return max(S - K, 0) if option_type == 'call' else max(K - S, 0)
        d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        if option_type == 'call':
            return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
        return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)