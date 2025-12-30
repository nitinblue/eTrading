# trading_bot/market_data/tastytrade_market_data.py
from typing import Dict
from tastytrade.instruments import get_option_chain
from market_data.storage import DataStorage  # Adjust path if needed
from market_data.abstract_market_data import MarketDataProvider
import logging

logger = logging.getLogger(__name__)

class TastytradeMarketData(MarketDataProvider):
    def __init__(self, session: any, use_storage: bool = True, storage_file: str = "market_data.json"):
        self.session = session
        self.use_storage = use_storage
        self.storage = DataStorage(storage_file) if use_storage else None

    def _key(self, *parts) -> str:
        return "_".join(map(str, parts))

    def get_option_greeks(self, underlying: str, expiry: str, strike: float, option_type: str, **kwargs) -> Dict:
        key = self._key("greeks", underlying, expiry, strike, option_type)
        if self.use_storage:
            stored = self.storage.load(key)
            if stored:
                return stored

        try:
            chain = get_option_chain(self.session, underlying)
            for exp_date, strikes in chain.items():
                if str(exp_date.date()) == expiry:
                    for opt in strikes:
                        if opt.strike_price == strike and opt.option_type == option_type.lower():
                            greeks = opt.greeks.to_dict() if hasattr(opt, 'greeks') and opt.greeks else {}
                            if self.use_storage:
                                self.storage.save(key, greeks)
                            return greeks
            return {}
        except Exception as e:
            logger.error(f"Tastytrade Greeks fetch failed: {e}")
            return {}

    def get_underlying_price(self, underlying: str, **kwargs) -> float:
        key = self._key("underlying_price", underlying)
        if self.use_storage:
            stored = self.storage.load(key)
            if stored is not None:
                return stored

        # Placeholder — use Equity.get or quote endpoint
        price = 200.0  # Replace with real fetch
        if self.use_storage:
            self.storage.save(key, price)
        return price

    def get_option_price(self, symbol: str, **kwargs) -> float:
        key = self._key("option_price", symbol)
        if self.use_storage:
            stored = self.storage.load(key)
            if stored is not None:
                return stored

        # Placeholder — fetch from chain or quote
        price = 5.0
        if self.use_storage:
            self.storage.save(key, price)
        return price