"""
Broker Adapter Base — Abstract interface all broker adapters must implement.

Provides:
    - BrokerAdapterBase: ABC with full method signatures
    - ManualBrokerAdapter: For brokers where user executes trades manually (Fidelity)
    - ReadOnlyAdapter: For fully managed funds (Stallion) — no trading at all

Usage:
    from trading_cotrader.adapters.base import BrokerAdapterBase
    adapter: BrokerAdapterBase = factory.create(broker_config)
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Optional
import logging

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class BrokerAdapterBase(ABC):
    """Interface ALL broker adapters must implement."""

    name: str = ""
    currency: str = "USD"
    is_authenticated: bool = False

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the broker. Returns True on success."""
        ...

    @abstractmethod
    def get_account_balance(self) -> Dict[str, Decimal]:
        """Get account balances (cash, buying power, NLV, etc.)."""
        ...

    @abstractmethod
    def get_positions(self) -> List[dm.Position]:
        """Get all positions with Greeks."""
        ...

    def get_option_chain(self, underlying: str) -> Any:
        """Get option chain for an underlying. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support option chains")

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get a single quote (bid/ask/mid). Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support quotes")

    def get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get quotes for multiple symbols. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support quotes")

    def get_greeks(self, symbols: List[str]) -> Dict[str, dm.Greeks]:
        """Get Greeks for multiple symbols. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support Greeks streaming")

    def get_public_watchlists(self, name: Optional[str] = None) -> Any:
        """Get public watchlists. Override in API-capable adapters.
        If name is None, returns list of available names.
        If name is given, returns the watchlist data."""
        raise NotImplementedError(f"{self.name} does not support watchlists")

    def place_order(
        self,
        legs: List[Dict[str, Any]],
        price: Decimal,
        order_type: str = "limit",
        time_in_force: str = "Day",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Place an order (or dry-run preflight) at the broker.

        Args:
            legs: List of dicts with keys: occ_symbol, action, quantity, instrument_type
            price: Net limit price (positive=debit, negative=credit)
            order_type: 'limit' only
            time_in_force: 'Day'
            dry_run: If True, validates without submitting

        Returns:
            Dict with order_id, status, buying_power_effect, fees, warnings, errors
        """
        raise NotImplementedError(f"{self.name} does not support order placement")

    def get_order(self, broker_order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order by broker order ID.

        Returns:
            Dict with order_id, status, legs, filled_quantity, average_fill_price
        """
        raise NotImplementedError(f"{self.name} does not support order queries")

    def get_live_orders(self) -> List[Dict[str, Any]]:
        """
        Get all live (working) orders at the broker.

        Returns:
            List of order dicts with order_id, status, legs, etc.
        """
        raise NotImplementedError(f"{self.name} does not support order queries")

    def get_transaction_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        underlying_symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get transaction history (fills, dividends, fees). Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support transaction history")

    def get_order_history(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        underlying_symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical orders. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support order history")

    def get_balance_snapshots(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Get daily balance snapshots for equity curve. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support balance snapshots")

    def get_net_liq_history(self, time_back: str = '1m') -> List[Dict[str, Any]]:
        """Get net liquidating value OHLC history. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support net liq history")

    def get_market_metrics(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get IV rank, IV percentile, beta, liquidity for symbols. Override in API-capable adapters."""
        raise NotImplementedError(f"{self.name} does not support market metrics")


class ManualBrokerAdapter(BrokerAdapterBase):
    """
    For brokers where user executes trades manually (e.g., Fidelity).

    Positions can be loaded via CSV import. API methods raise NotImplementedError.
    """

    def __init__(self, broker_name: str, currency: str = "USD"):
        self.name = broker_name
        self.currency = currency
        self.is_authenticated = True  # No auth needed for manual

    def authenticate(self) -> bool:
        logger.info(f"[{self.name}] Manual broker — no authentication needed")
        self.is_authenticated = True
        return True

    def get_account_balance(self) -> Dict[str, Decimal]:
        logger.debug(f"[{self.name}] Manual broker — balances from CSV import only")
        return {}

    def get_positions(self) -> List[dm.Position]:
        logger.debug(f"[{self.name}] Manual broker — positions from CSV import only")
        return []


class ReadOnlyAdapter(BrokerAdapterBase):
    """
    For fully managed funds (e.g., Stallion) — no trading at all.

    All methods return empty results. Holdings loaded via CLI tools.
    """

    def __init__(self, broker_name: str, currency: str = "INR"):
        self.name = broker_name
        self.currency = currency
        self.is_authenticated = True  # No auth needed

    def authenticate(self) -> bool:
        logger.info(f"[{self.name}] Read-only fund — no authentication needed")
        self.is_authenticated = True
        return True

    def get_account_balance(self) -> Dict[str, Decimal]:
        return {}

    def get_positions(self) -> List[dm.Position]:
        return []
