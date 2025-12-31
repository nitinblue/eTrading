# trading_bot/market_data/__init__.py
"""Market data package."""

from .abstract_market_data import MarketDataProvider  # Expose the abstract class

# Optional: expose specific implementations
# from .tastytrade_market_data import TastytradeMarketData
# from .calculator import BlackScholesCalculator

__all__ = ['MarketDataProvider']