"""
Broker Factory — Creates MA providers for any supported broker.

Supports:
  - TastyTrade (US) — session token or username/password
  - Dhan (India) — API key + access token
  - Zerodha (India) — Kite Connect API key + access token

All brokers return the same 4-tuple:
  (MarketDataProvider, MarketMetricsProvider, AccountProvider, WatchlistProvider)

eTrading owns auth. MA gets pre-authenticated providers.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Broker metadata
BROKER_REGISTRY = {
    'tastytrade': {
        'market': 'US',
        'currency': 'USD',
        'timezone': 'US/Eastern',
        'display_name': 'TastyTrade',
        'auth_type': 'session_token',  # or username/password
    },
    'dhan': {
        'market': 'INDIA',
        'currency': 'INR',
        'timezone': 'Asia/Kolkata',
        'display_name': 'Dhan',
        'auth_type': 'api_key_token',
    },
    'zerodha': {
        'market': 'INDIA',
        'currency': 'INR',
        'timezone': 'Asia/Kolkata',
        'display_name': 'Zerodha (Kite)',
        'auth_type': 'api_key_token',
    },
}


def get_supported_brokers() -> dict:
    """Return metadata for all supported brokers."""
    return BROKER_REGISTRY.copy()


def create_providers(
    broker_name: str,
    credentials: dict,
) -> Tuple:
    """Create MA providers for any supported broker.

    Args:
        broker_name: 'tastytrade', 'dhan', or 'zerodha'
        credentials: Broker-specific auth data:
            - tastytrade: {'username': str, 'password': str} or {'session': sdk_session}
            - dhan: {'api_key': str, 'access_token': str}
            - zerodha: {'api_key': str, 'access_token': str}

    Returns:
        4-tuple: (MarketDataProvider, MarketMetricsProvider, AccountProvider, WatchlistProvider)

    Raises:
        ValueError: Unknown broker or missing credentials
    """
    if broker_name not in BROKER_REGISTRY:
        raise ValueError(f"Unknown broker: {broker_name}. Supported: {list(BROKER_REGISTRY.keys())}")

    if broker_name == 'tastytrade':
        return _connect_tastytrade(credentials)
    elif broker_name == 'dhan':
        return _connect_dhan(credentials)
    elif broker_name == 'zerodha':
        return _connect_zerodha(credentials)


def _connect_tastytrade(credentials: dict) -> Tuple:
    """Connect to TastyTrade."""
    from market_analyzer.broker.tastytrade import connect_from_sessions, connect_tastytrade

    if 'session' in credentials:
        # Pre-authenticated session (SaaS pattern)
        data_session = credentials.get('data_session')
        return connect_from_sessions(credentials['session'], data_session)
    else:
        # Standalone mode (username/password from config)
        return connect_tastytrade()


def _connect_dhan(credentials: dict) -> Tuple:
    """Connect to Dhan."""
    from market_analyzer.broker.dhan import connect_dhan

    api_key = credentials.get('api_key')
    access_token = credentials.get('access_token')

    if not api_key or not access_token:
        raise ValueError("Dhan requires 'api_key' and 'access_token'")

    return connect_dhan(api_key, access_token)


def _connect_zerodha(credentials: dict) -> Tuple:
    """Connect to Zerodha."""
    from market_analyzer.broker.zerodha import connect_zerodha

    api_key = credentials.get('api_key')
    access_token = credentials.get('access_token')

    if not api_key or not access_token:
        raise ValueError("Zerodha requires 'api_key' and 'access_token'")

    return connect_zerodha(api_key, access_token)


def get_broker_info(broker_name: str) -> Optional[dict]:
    """Get broker metadata."""
    return BROKER_REGISTRY.get(broker_name)
