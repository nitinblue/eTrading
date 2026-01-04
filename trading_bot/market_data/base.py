# trading_bot/market_data/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class MarketDataProvider(ABC):
    """Abstract base for market data providers."""

    @abstractmethod
    def get_option_chain(self, underlying: str) -> Dict:
        """Return full option chain."""
        pass

    @abstractmethod
    def get_underlying_price(self, underlying: str) -> float:
        """Return current underlying price."""
        pass

    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> List[Dict]:
        """Return quotes for list of symbols (options or equity)."""
        pass