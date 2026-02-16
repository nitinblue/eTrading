"""
Broker Router — Routes trade execution to the correct broker handler.

Safety invariants:
    1. Cross-broker routing: Fidelity trade NEVER routes to Tastytrade API
    2. Currency isolation: USD trade cannot land in INR portfolio
    3. Manual execution: Fidelity/Stallion trades return MANUAL status
    4. Data broker per currency: USD → Tastytrade, INR → Zerodha

Usage:
    router = BrokerRouter(broker_registry, adapters={'tastytrade': tt_adapter})
    result = router.execute(action, portfolio_config)
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import logging

from trading_cotrader.config.broker_config_loader import BrokerRegistry, BrokerConfig
from trading_cotrader.config.risk_config_loader import PortfolioConfig

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool = False
    blocked: bool = False
    manual: bool = False
    message: str = ""
    trade_id: str = ""
    data: Dict = field(default_factory=dict)


class BrokerRouter:
    """Routes trade execution to the correct broker handler."""

    def __init__(self, broker_registry: BrokerRegistry, adapters: Dict = None):
        """
        Args:
            broker_registry: BrokerRegistry loaded from brokers.yaml
            adapters: Dict mapping broker name → adapter instance
                      e.g. {'tastytrade': TastytradeAdapter}
        """
        self.registry = broker_registry
        self.adapters = adapters or {}

    def execute(self, action: dict, portfolio_config: PortfolioConfig) -> ExecutionResult:
        """
        Route a trade action to the correct broker.

        Args:
            action: Dict with trade details (recommendation_id, summary, etc.)
            portfolio_config: The portfolio this trade belongs to.

        Returns:
            ExecutionResult with success/blocked/manual status.
        """
        broker_name = portfolio_config.broker_firm
        broker_cfg = self.registry.get_by_name(broker_name)

        if not broker_cfg:
            return ExecutionResult(
                blocked=True,
                message=f"Unknown broker: {broker_name}"
            )

        # Safety: read-only fund (Stallion) — no execution at all
        if broker_cfg.read_only:
            return ExecutionResult(
                blocked=True,
                message=f"{broker_cfg.display_name} is a fully managed fund — "
                        f"trade execution is not available."
            )

        # Safety: cross-broker routing check
        valid, reason = self._validate_routing(action, portfolio_config, broker_cfg)
        if not valid:
            return ExecutionResult(blocked=True, message=reason)

        # Manual execution (Fidelity)
        if broker_cfg.manual_execution:
            return self._manual_execution(action, portfolio_config, broker_cfg)

        # API execution (Tastytrade, Zerodha)
        adapter = self.adapters.get(broker_name)
        if not adapter:
            return ExecutionResult(
                blocked=True,
                message=f"No adapter loaded for {broker_cfg.display_name}. "
                        f"Trade must be executed manually."
            )

        return self._api_execution(action, adapter, portfolio_config, broker_cfg)

    def _validate_routing(
        self,
        action: dict,
        portfolio_config: PortfolioConfig,
        broker_cfg: BrokerConfig,
    ) -> tuple[bool, str]:
        """Validate that routing is safe."""
        # Currency mismatch check
        action_currency = action.get('currency', portfolio_config.currency)
        if action_currency != portfolio_config.currency:
            return False, (
                f"Currency mismatch: action currency {action_currency} "
                f"does not match portfolio currency {portfolio_config.currency}"
            )

        # Cross-broker check: if an adapter is specified in the action,
        # it must match the portfolio's broker
        action_broker = action.get('target_broker')
        if action_broker and action_broker != portfolio_config.broker_firm:
            return False, (
                f"Cross-broker routing blocked: action targets {action_broker} "
                f"but portfolio belongs to {portfolio_config.broker_firm}"
            )

        return True, ""

    def _manual_execution(
        self,
        action: dict,
        portfolio_config: PortfolioConfig,
        broker_cfg: BrokerConfig,
    ) -> ExecutionResult:
        """Log trade details for user to execute manually at their broker."""
        summary = action.get('summary', 'Trade details not provided')
        message = (
            f"MANUAL EXECUTION REQUIRED at {broker_cfg.display_name}\n"
            f"  Account: {portfolio_config.account_number}\n"
            f"  {summary}\n"
            f"  Please execute this trade at your broker and confirm."
        )
        logger.info(message)
        return ExecutionResult(
            manual=True,
            message=message,
            data={'broker': broker_cfg.name, 'account': portfolio_config.account_number},
        )

    def _api_execution(
        self,
        action: dict,
        adapter,
        portfolio_config: PortfolioConfig,
        broker_cfg: BrokerConfig,
    ) -> ExecutionResult:
        """Send order via broker API (future — currently books as WhatIf)."""
        # For now, all API execution is paper mode — adapter.place_order() not yet implemented
        logger.info(
            f"API execution via {broker_cfg.display_name} "
            f"account={portfolio_config.account_number}"
        )
        return ExecutionResult(
            success=True,
            message=f"Routed to {broker_cfg.display_name} API",
            data={'broker': broker_cfg.name, 'account': portfolio_config.account_number},
        )

    def get_data_broker(self, currency: str):
        """Get data broker adapter for a currency (USD→Tastytrade, INR→Zerodha)."""
        broker_cfg = self.registry.get_data_broker(currency)
        if not broker_cfg:
            return None
        return self.adapters.get(broker_cfg.name)

    def is_manual_broker(self, broker_name: str) -> bool:
        """Check if a broker requires manual execution."""
        cfg = self.registry.get_by_name(broker_name)
        return cfg.manual_execution if cfg else False
