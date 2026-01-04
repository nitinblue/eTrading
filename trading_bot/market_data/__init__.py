# trading_bot/market_data/__init__.py
from .tastytrade import TastytradeMarketData
from trading_bot.config import Config
import logging

logger = logging.getLogger(__name__)

_instance = None

def get_market_data_provider():
    """Singleton — always live Tastytrade for market data."""
    global _instance
    if _instance is None:
        config = Config.load('config.yaml')
        _instance = TastytradeMarketData(config)
    return _instance