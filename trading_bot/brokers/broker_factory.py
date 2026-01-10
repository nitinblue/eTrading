# trading_bot/brokers/broker_factory.py
"""
Broker Factory — creates broker instances dynamically.
- Supports override via broker_name param.
- Config-driven credentials/mode.
- Easy to add new brokers.
"""

from typing import Dict, Any
import logging

from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.brokers.zerodha_broker import ZerodhaBroker
from trading_bot.brokers.dhan_broker import DhanBroker

logger = logging.getLogger(__name__)

BROKER_REGISTRY = {
    'tastytrade': TastytradeBroker,
    'zerodha': ZerodhaBroker,
    'dhan': DhanBroker,
}

def create_broker(config: Dict, broker_name: str = None, mode: str = None) -> Any:
    """
    Create broker instance.
    - broker_name: Override config (e.g., 'zerodha')
    - mode: Override config (e.g., 'live')
    """
    broker_name = broker_name or config.get('general', {}).get('broker', broker_name).lower()
    logging.info(f"Creating broker: {broker_name}")
    broker_class = BROKER_REGISTRY.get(broker_name)
    if not broker_class:
        raise ValueError(f"Unknown broker '{broker_name}'. Supported: {list(BROKER_REGISTRY.keys())}")

    mode = mode or config.get('general', {}).get('execution_mode', 'is_paper').lower()
    logging.info(f"Broker mode from broker_factory: {mode}")
    creds_key = 'live' if mode == 'live' else 'paper'
    
    creds = config.get('broker', {}).get(broker_name, {}).get(creds_key, {})
    logging.info(f"Broker credentials for {broker_name} in mode '{creds_key}': {creds}")
    if not creds:
        raise ValueError(f"No credentials for {broker_name} in mode '{creds_key}'")

    try:
        broker = broker_class(**creds, is_paper=(mode == 'paper'))
        logger.info(f"Created {broker_name} broker in {mode} mode")
        return broker
    except Exception as e:
        logger.error(f"Failed to create {broker_name}: {e}")
        raise