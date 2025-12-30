# trading_bot/market_data/abstract_market_data.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class MarketDataProvider(ABC):
    @abstractmethod
    def get_option_greeks(self, underlying: str, expiry: str, strike: float, option_type: str, **kwargs) -> Dict:
        pass

    @abstractmethod
    def get_underlying_price(self, underlying: str, **kwargs) -> float:
        pass

    @abstractmethod
    def get_option_price(self, symbol: str, **kwargs) -> float:
        pass