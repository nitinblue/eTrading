"""
Broker Adapter Factory — Creates adapters from BrokerConfig.

Usage:
    from trading_cotrader.adapters.factory import BrokerAdapterFactory
    adapter = BrokerAdapterFactory.create(broker_config)
    all_api = BrokerAdapterFactory.create_all_api(registry)
"""

from typing import Dict, Optional
import logging

from trading_cotrader.adapters.base import BrokerAdapterBase, ManualBrokerAdapter, ReadOnlyAdapter
from trading_cotrader.config.broker_config_loader import BrokerConfig, BrokerRegistry

logger = logging.getLogger(__name__)


class BrokerAdapterFactory:
    """Creates broker adapters from configuration."""

    @classmethod
    def create(cls, broker_config: BrokerConfig, **kwargs) -> BrokerAdapterBase:
        """
        Create an adapter for a given broker config.

        Args:
            broker_config: BrokerConfig from brokers.yaml
            **kwargs: Extra args passed to adapter constructor (e.g., account_number, is_paper)

        Returns:
            BrokerAdapterBase instance
        """
        if broker_config.read_only:
            return ReadOnlyAdapter(
                broker_name=broker_config.name,
                currency=broker_config.currency,
            )

        if broker_config.manual_execution:
            return ManualBrokerAdapter(
                broker_name=broker_config.name,
                currency=broker_config.currency,
            )

        if broker_config.adapter == "tastytrade":
            from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
            return TastytradeAdapter(
                account_number=kwargs.get('account_number'),
                is_paper=kwargs.get('is_paper', False),
            )

        # Default: manual adapter as fallback
        logger.warning(f"No adapter mapping for '{broker_config.adapter}', using ManualBrokerAdapter")
        return ManualBrokerAdapter(
            broker_name=broker_config.name,
            currency=broker_config.currency,
        )

    @classmethod
    def create_all_api(cls, registry: BrokerRegistry, **kwargs) -> Dict[str, BrokerAdapterBase]:
        """
        Create adapters only for API-capable brokers.

        Returns:
            Dict mapping broker name to adapter instance.
        """
        adapters: Dict[str, BrokerAdapterBase] = {}
        for bc in registry.get_all():
            if bc.has_api:
                try:
                    adapter = cls.create(bc, **kwargs)
                    adapters[bc.name] = adapter
                    logger.info(f"Created adapter for {bc.name} ({bc.currency})")
                except Exception as e:
                    logger.error(f"Failed to create adapter for {bc.name}: {e}")
        return adapters
