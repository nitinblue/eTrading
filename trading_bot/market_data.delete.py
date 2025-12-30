# trading_bot/market_data.py
from abc import ABC, abstractmethod
from typing import Dict
from tastytrade.instruments import get_option_chain
from scipy.stats import norm
from math import log, sqrt, exp
from .data_storage import DataStorage  # Assume you have this
import logging

logger = logging.getLogger(__name__)

class MarketDataProvider(ABC):
    @abstractmethod
    def get_option_greeks(self, underlying: str, expiry: str, strike: float, option_type: str, session: Any) -> Dict:
        pass

class TastytradeMarketData(MarketDataProvider):
    def __init__(self, use_api: bool, storage_file: str = "data_storage.json"):
        self.use_api = use_api
        self.storage = DataStorage(storage_file)

    def get_option_greeks(self, underlying: str, expiry: str, strike: float, option_type: str, session: Any) -> Dict:
        key = f"{underlying}_{expiry}_{strike}_{option_type}"
        if not self.use_api:
            stored = self.storage.load(key)
            if stored:
                logger.info(f"Loaded Greeks from storage for {key}")
                return stored
            logger.warning(f"No stored data for {key}; falling back to Python calc")
            return BlackScholesCalculator().calculate_greeks(S=200.0, K=strike, T=30/365, r=0.05, sigma=0.3, option_type=option_type)  # Example params; use real

        try:
            chain = get_option_chain(session, underlying)
            for exp_date, strikes in chain.items():
                if str(exp_date.date()) == expiry:
                    for opt in strikes:
                        if opt.strike_price == strike and opt.option_type == option_type.lower():
                            greeks = opt.greeks.to_dict() if hasattr(opt, 'greeks') and opt.greeks else {}
                            self.storage.save(key, greeks)  # Store after fetch
                            return greeks
            return {}
        except Exception as e:
            logger.error(f"Greeks fetch failed: {e}")
            return {}

class BlackScholesCalculator:
    def calculate_greeks(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> Dict:
        d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        if option_type == 'call':
            delta = norm.cdf(d1)
            gamma = norm.pdf(d1) / (S * sigma * sqrt(T))
            vega = S * norm.pdf(d1) * sqrt(T)
            theta = - (S * norm.pdf(d1) * sigma) / (2 * sqrt(T)) - r * K * exp(-r * T) * norm.cdf(d2)
            rho = K * T * exp(-r * T) * norm.cdf(d2)
        else:
            delta = -norm.cdf(-d1)
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