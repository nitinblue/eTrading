# trading_bot/market_data/tastytrade.py
from .base import MarketDataProvider
from tastytrade import Session
from tastytrade.instruments import get_option_chain
from tastytrade.market_data import get_market_data_by_type
import logging

logger = logging.getLogger(__name__)

class TastytradeMarketData(MarketDataProvider):
    """Tastytrade implementation — uses LIVE for real data."""

    def __init__(self, config):
        self.config = config
        self.session = None
        self._connect()

    def _connect(self):
        creds = self.config.broker.get('live', {})  # Always live for data
        if not creds:
            raise ValueError("Live broker credentials missing for market data")

        try:
            self.session = Session(
                provider_secret=creds['client_secret'],
                refresh_token=creds['refresh_token'],
                is_test=False
            )
            logger.info("TastytradeMarketData: Connected to LIVE for market data")
        except Exception as e:
            logger.error(f"TastytradeMarketData connection failed: {e}")
            raise

    def get_option_chain(self, underlying: str):
        return get_option_chain(self.session, underlying)

    def get_underlying_price(self, underlying: str) -> float:
        quotes = self.get_quotes([underlying])
        if quotes and quotes[0]:
            quote = quotes[0]
            return float(quote.get('last_price') or quote.get('close_price') or quote.get('bid_price') or 0.0)
        return 0.0

    def get_quotes(self, symbols: List[str]) -> List[Dict]:
        """Use your working get_market_data_by_type."""
        try:
            response = get_market_data_by_type(self.session, options=symbols)
            # Paper mode sometimes has different structure — handle both
            items = response.get('items', response)  # Fallback if no 'items'
            return items
        except Exception as e:
            logger.warning(f"get_market_data_by_type failed: {e}")
            return []