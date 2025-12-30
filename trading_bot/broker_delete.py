# trading_bot/broker.py
"""
Broker implementations for the trading bot.
Contains TastytradeBroker and MockBroker.
Order model is imported from order_model.py.
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal

# Tastytrade SDK - current non-deprecated imports
from tastytrade.certifier import Certifier
from tastytrade.session import AuthenticatedSession
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect

# Our universal order model
from .order_model import UniversalOrder, OrderLeg

import logging

logger = logging.getLogger(__name__)

# ========================
# Mock Broker (for testing/dry runs)
# ========================

class MockBroker:
    """Mock broker for dry runs and testing."""
    def __init__(self, mock_positions: Optional[Dict[str, List[Dict]]] = None, mock_balances: Optional[Dict[str, Dict]] = None):
        self.mock_positions = mock_positions or {
            'default_account': []  # Start empty to avoid risk error
        }
        self.mock_balances = mock_balances or {
            'default_account': {
                'cash_balance': 100000.0,
                'buying_power': 200000.0,
                'equity': 150000.0
            }
        }
        self.order_history: Dict[str, List[Dict]] = {}
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        logger.info("[MOCK] Connected to broker.")

    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.connected:
            raise RuntimeError("[MOCK] Broker not connected.")
        acc_id = account_id or 'default_account'
        return self.mock_positions.get(acc_id, [])

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict:
        if not self.connected:
            raise RuntimeError("[MOCK] Broker not connected.")
        acc_id = account_id or 'default_account'
        return self.mock_balances.get(acc_id, {})

    def execute_order(self, order: UniversalOrder, account_id: Optional[str] = None) -> Dict:
        if not self.connected:
            raise RuntimeError("[MOCK] Broker not connected.")
        acc_id = account_id or 'default_account'
        if acc_id not in self.order_history:
            self.order_history[acc_id] = []

        if order.dry_run:
            logger.info(f"[MOCK DRY RUN] Would execute on {acc_id}: {order.to_dict()}")
            return {"status": "mock_dry_run_success", "order": order.to_dict()}

        # Simulate execution
        self.order_history[acc_id].append(order.to_dict())
        for leg in order.legs:
            mock_pos = {
                'symbol': leg.symbol,
                'quantity': leg.quantity if "BUY" in leg.action.value else -leg.quantity,
                'entry_price': 0.0,
                'current_price': 0.0,
                'greeks': {}
            }
            if acc_id not in self.mock_positions:
                self.mock_positions[acc_id] = []
            self.mock_positions[acc_id].append(mock_pos)

        logger.info(f"[MOCK] Executed on {acc_id}: {order.to_dict()}")
        return {"status": "mock_success", "order_id": len(self.order_history[acc_id]), "details": order.to_dict()}


# ========================
# Tastytrade Broker
# ========================

class TastytradeBroker:
    def __init__(self, username: str, password: str, is_paper: bool = True):
        self.username = username
        self.password = password
        self.is_paper = is_paper
        self.certifier: Optional[Certifier] = None
        self.session: Optional[AuthenticatedSession] = None
        self.accounts: Dict[str, Account] = {}

    def connect(self) -> None:
        try:
            # New authentication flow
            self.certifier = Certifier.login(self.username, self.password)
            self.session = AuthenticatedSession(self.certifier, test=self.is_paper)
            logger.info(f"Connected to Tastytrade {'PAPER' if self.is_paper else 'LIVE'} environment (new auth flow).")

            accounts_list = Account.get_accounts(self.session)
            self.accounts = {acc.account_number: acc for acc in accounts_list}
            logger.info(f"Loaded {len(self.accounts)} account(s).")
        except Exception as e:
            logger.error(f"Tastytrade connection failed: {e}")
            raise

    # _get_account, get_positions, get_account_balance — unchanged (use self.session)

    def execute_order(self, order: UniversalOrder, account_id: Optional[str] = None) -> Dict:
        if not self.session:
            raise RuntimeError("Broker not connected.")
        account = self._get_account(account_id)

        if order.dry_run:
            logger.info(f"[DRY RUN] Account {account.account_number}: {order.to_dict()}")
            return {"status": "dry_run_success", "order": order.to_dict()}

        try:
            legs = []
            for leg in order.legs:
                instrument = Option.get_option(self.session, leg.symbol)
                legs.append(instrument.build_leg(Decimal(leg.quantity), getattr(OrderAction, leg.action.value)))

            tt_order = NewOrder(
                time_in_force=getattr(OrderTimeInForce, order.time_in_force),
                order_type=getattr(OrderType, order.order_type.value),
                legs=legs,
                price=Decimal(str(order.limit_price)) if order.limit_price else None
            )

            if tt_order.price is not None:
                tt_order.price = abs(tt_order.price) if order.price_effect == PriceEffect.CREDIT else -abs(tt_order.price)

            response = account.place_order(self.session, tt_order)
            logger.info(f"Order placed on {account.account_number}")
            return {"status": "success", "details": str(response)}
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"status": "failed", "error": str(e)}