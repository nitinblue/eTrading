"""
Zerodha Adapter — Kite Connect integration for India market.

Credentials from env vars only (no YAML):
  ZERODHA_API_KEY     — Kite Connect API key
  ZERODHA_ACCESS_TOKEN — Daily access token (expires EOD, re-auth required)

Usage:
    adapter = ZerodhaAdapter()
    adapter.authenticate()
    providers = adapter.get_market_providers()
    # → (ZerodhaMarketData, ZerodhaMetrics, ZerodhaAccount, ZerodhaWatchlist)
"""

import os
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class ZerodhaAdapter:
    """Zerodha Kite Connect broker adapter."""

    def __init__(self, read_only: bool = True):
        self.name = 'zerodha'
        self.currency = 'INR'
        self.timezone = 'Asia/Kolkata'
        self.market = 'INDIA'
        self._read_only = read_only
        self.api_key = None
        self.access_token = None
        self._providers = None
        self._authenticated = False

        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from environment variables."""
        self.api_key = os.getenv('ZERODHA_API_KEY')
        self.access_token = os.getenv('ZERODHA_ACCESS_TOKEN')

        if self.api_key and self.access_token:
            logger.info("Zerodha credentials loaded from env vars")
        else:
            logger.debug("Zerodha credentials not found in env vars")

    def authenticate(self) -> bool:
        """Authenticate with Zerodha via Kite Connect."""
        if not self.api_key or not self.access_token:
            logger.warning("Zerodha: missing API_KEY or ACCESS_TOKEN")
            return False

        try:
            from market_analyzer.broker.zerodha import connect_zerodha
            self._providers = connect_zerodha(self.api_key, self.access_token)
            self._authenticated = True
            logger.info("Zerodha: authenticated successfully")
            return True
        except Exception as e:
            logger.error(f"Zerodha authentication failed: {e}")
            return False

    def get_market_providers(self) -> Tuple:
        """Return (MarketDataProvider, MetricsProvider, AccountProvider, WatchlistProvider)."""
        if not self._authenticated or not self._providers:
            raise ValueError("Not authenticated — call authenticate() first")
        return self._providers

    def is_token_valid(self) -> bool:
        """Check if Zerodha access token is still valid.

        Zerodha tokens expire daily. User must re-authenticate each morning.
        """
        if not self._providers:
            return False
        try:
            md = self._providers[0]
            if hasattr(md, 'is_token_valid'):
                return md.is_token_valid()
            return self._authenticated
        except Exception:
            return False

    @property
    def account_id(self) -> str:
        """Return account identifier."""
        return self.api_key[:8] if self.api_key else ''

    # -----------------------------------------------------------------
    # Zerodha OAuth Flow — Interactive Login
    # -----------------------------------------------------------------

    @staticmethod
    def get_login_url(api_key: str = None) -> str:
        """Get Zerodha login URL for OAuth2 redirect.

        User opens this URL → logs in on Zerodha → gets redirected with request_token.

        Steps:
          1. Call get_login_url() → open in browser
          2. User logs in on Zerodha website
          3. Zerodha redirects to your callback URL with ?request_token=xxx
          4. Call complete_login(request_token) to get access_token
          5. Store access_token in env or DB
        """
        key = api_key or os.getenv('ZERODHA_API_KEY', '')
        if not key:
            return "ERROR: Set ZERODHA_API_KEY first"
        return f"https://kite.zerodha.com/connect/login?v=3&api_key={key}"

    @staticmethod
    def complete_login(request_token: str, api_key: str = None, api_secret: str = None) -> Optional[str]:
        """Exchange request_token for access_token.

        Args:
            request_token: From Zerodha redirect URL (?request_token=xxx)
            api_key: Kite Connect API key
            api_secret: Kite Connect API secret

        Returns:
            access_token string (valid for 1 day), or None on failure
        """
        key = api_key or os.getenv('ZERODHA_API_KEY', '')
        secret = api_secret or os.getenv('ZERODHA_API_SECRET', '')

        if not key or not secret:
            logger.error("Missing ZERODHA_API_KEY or ZERODHA_API_SECRET")
            return None

        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=key)
            data = kite.generate_session(request_token, api_secret=secret)
            access_token = data['access_token']
            logger.info(f"Zerodha login successful. Token valid until EOD.")
            return access_token
        except ImportError:
            logger.error("kiteconnect package not installed. Run: pip install kiteconnect")
            return None
        except Exception as e:
            logger.error(f"Zerodha login failed: {e}")
            return None
