# trading_bot/market_data.py
from abc import ABC, abstractmethod
from typing import Dict

# Remove streamer import if not using async/real-time in sync code
# from tastytrade import DXLinkStreamer  # This is async; keep if you plan async version

from tastytrade.instruments import Option  # For static greeks
from scipy.stats import norm
from math import log, sqrt, exp

class MarketDataProvider(ABC):
    """Abstract for market data. Configurable sources."""
    @abstractmethod
    def get_option_greeks(self, symbol: str, expiry: str, strike: float, option_type: str, session) -> Dict:
        pass

    @abstractmethod
    def get_real_time_quote(self, symbol: str, session) -> Dict:
        pass

class TastytradeMarketData(MarketDataProvider):
    """Uses Tastytrade SDK for static data (greeks from option object)."""
    def get_option_greeks(self, underlying: str, expiry: str, strike: float, option_type: str, session) -> Dict:
        """Fetch greeks from option chain/object (static, not streamed)."""
        from tastytrade.instruments import get_option_chain
        
        chain = get_option_chain(session, underlying)
        # Find the specific option (simplified; iterate or use chain[expiry][strike])
        for exp_date, strikes in chain.items():
            if str(exp_date.date()) == expiry:  # Match expiry
                for opt in strikes:
                    if opt.strike_price == strike and opt.option_type == option_type.lower():
                        return opt.greeks.to_dict() if hasattr(opt, 'greeks') and opt.greeks else {}
        return {}

    def get_real_time_quote(self, symbol: str, session) -> Dict:
        """Placeholder for real-time; streaming is async."""
        # For sync, use search or other endpoint; or return mock
        # Streaming requires async DXLinkStreamer
        return {"bid": 0.0, "ask": 0.0, "last": 0.0}  # Placeholder

class BlackScholesCalculator:
    """Standalone for pricing/Greeks if API unavailable."""
    def calculate_price(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> float:
        d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        if option_type == 'call':
            return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
        else:  # put
            return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    def calculate_greeks(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> Dict:
        d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        if option_type == 'call':
            delta = norm.cdf(d1)
            gamma = norm.pdf(d1) / (S * sigma * sqrt(T))
            vega = S * norm.pdf(d1) * sqrt(T)
            theta = - (S * norm.pdf(d1) * sigma) / (2 * sqrt(T)) - r * K * exp(-r * T) * norm.cdf(d2)
            rho = K * T * exp(-r * T) * norm.cdf(d2)
        else:  # put
            delta = -norm.cdf(-d1)
            gamma = norm.pdf(d1) / (S * sigma * sqrt(T))
            vega = S * norm.pdf(d1) * sqrt(T)
            theta = - (S * norm.pdf(d1) * sigma) / (2 * sqrt(T)) + r * K * exp(-r * T) * norm.cdf(-d2)
            rho = -K * T * exp(-r * T) * norm.cdf(-d2)
        return {
            'delta': delta,
            'gamma': gamma,
            'vega': vega / 100,  # Per 1% usually
            'theta': theta / 365,  # Per day
            'rho': rho / 100  # Per 1%
        }