"""
Broker Configuration Loader — Loads brokers.yaml into typed dataclasses.

Provides BrokerConfig per brokerage and BrokerRegistry for lookups.

Usage:
    from trading_cotrader.config.broker_config_loader import load_broker_registry
    registry = load_broker_registry()
    tt = registry.get_by_name('tastytrade')
    data_broker = registry.get_data_broker('USD')
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class BrokerConfig:
    """Configuration for a single brokerage."""
    name: str                        # internal key (e.g. "tastytrade")
    display_name: str = ""
    currency: str = "USD"            # "USD" or "INR"
    has_api: bool = False
    is_data_broker: bool = False     # default data source for its currency
    manual_execution: bool = False   # user executes trades manually
    read_only: bool = False          # fully managed fund — no trade execution at all
    adapter: str = ""                # adapter class key (e.g. "tastytrade")


@dataclass
class BrokerRegistry:
    """Container for all broker configurations."""
    brokers: Dict[str, BrokerConfig] = field(default_factory=dict)

    def get_by_name(self, name: str) -> Optional[BrokerConfig]:
        """Get broker config by internal name."""
        return self.brokers.get(name)

    def get_data_broker(self, currency: str) -> Optional[BrokerConfig]:
        """Get the default data broker for a currency (USD -> Tastytrade, INR -> Zerodha)."""
        for bc in self.brokers.values():
            if bc.currency == currency and bc.is_data_broker:
                return bc
        return None

    def get_all(self) -> List[BrokerConfig]:
        """Get all broker configs."""
        return list(self.brokers.values())

    def get_by_currency(self, currency: str) -> List[BrokerConfig]:
        """Get all brokers for a given currency."""
        return [bc for bc in self.brokers.values() if bc.currency == currency]


# Default search paths
_DEFAULT_PATHS = [
    Path('config/brokers.yaml'),
    Path(__file__).parent / 'brokers.yaml',
    Path(__file__).parent.parent / 'config' / 'brokers.yaml',
]


def load_broker_registry(config_path: str = None) -> BrokerRegistry:
    """
    Load broker registry from YAML.

    Args:
        config_path: Explicit path. If None, searches default locations.

    Returns:
        BrokerRegistry with all brokers loaded.
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Broker config not found: {config_path}")
    else:
        path = _find_config_file()

    logger.info(f"Loading broker config from: {path}")
    with open(path, 'r') as f:
        raw = yaml.safe_load(f)

    brokers_dict = {}
    for name, data in raw.get('brokers', {}).items():
        brokers_dict[name] = BrokerConfig(
            name=name,
            display_name=data.get('display_name', name),
            currency=data.get('currency', 'USD'),
            has_api=data.get('has_api', False),
            is_data_broker=data.get('is_data_broker', False),
            manual_execution=data.get('manual_execution', False),
            read_only=data.get('read_only', False),
            adapter=data.get('adapter', ''),
        )

    registry = BrokerRegistry(brokers=brokers_dict)
    logger.info(f"Loaded {len(brokers_dict)} broker configs")
    return registry


def _find_config_file() -> Path:
    """Find config file in default locations."""
    for p in _DEFAULT_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Broker config not found. Tried: {[str(p) for p in _DEFAULT_PATHS]}"
    )


# Singleton
_broker_registry: Optional[BrokerRegistry] = None


def get_broker_registry() -> BrokerRegistry:
    """Get global broker registry (singleton)."""
    global _broker_registry
    if _broker_registry is None:
        _broker_registry = load_broker_registry()
    return _broker_registry
