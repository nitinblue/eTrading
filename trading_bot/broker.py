# trading_bot/broker.py
comment = '''\
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from decimal import Decimal

from tastytrade import Session
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder,OrderTimeInForce

# Import everything needed from broker.py
from trading_bot.broker import (
    Broker,
    NeutralOrder,
    OrderLeg,
    OrderAction,
    PriceEffect,     # <-- Now correctly available
    OrderType
)
import logging

close comment '''

# trading_bot/broker.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from decimal import Decimal

from tastytrade import Session
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect
import logging
logger = logging.getLogger(__name__)

# ========================
# Broker-Neutral Order Model
# ========================

class OrderAction(Enum):
    BUY_TO_OPEN = "BUY_TO_OPEN"
    BUY_TO_CLOSE = "BUY_TO_CLOSE"
    SELL_TO_OPEN = "SELL_TO_OPEN"
    SELL_TO_CLOSE = "SELL_TO_CLOSE"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

@dataclass
class OrderLeg:
    symbol: str
    quantity: int
    action: OrderAction

@dataclass
class NeutralOrder:
    legs: List[OrderLeg]
    price_effect: PriceEffect  # Now correctly imported, no error
    order_type: OrderType = OrderType.LIMIT
    limit_price: Optional[float] = None
    time_in_force: str = "DAY"
    dry_run: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "legs": [{"symbol": leg.symbol, "quantity": leg.quantity, "action": leg.action.value} for leg in self.legs],
            "price_effect": self.price_effect.value,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "time_in_force": self.time_in_force,
            "dry_run": self.dry_run
        }

# ========================
# Abstract Broker Interface
# ========================

class Broker(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        pass

    @abstractmethod
    def get_account_balance(self, account_id: Optional[str] = None) -> Dict:
        pass

    @abstractmethod
    def execute_order(self, order: NeutralOrder, account_id: Optional[str] = None) -> Dict:
        pass

# ========================
# Tastytrade Broker
# ========================

class TastytradeBroker(Broker):
    def __init__(self, username: str, password: str, is_paper: bool = True, remember_me: bool = True):
        self.username = username
        self.password = password
        self.is_paper = is_paper
        self.remember_me = remember_me
        self.session: Optional[Session] = None
        self.accounts: Dict[str, Account] = {}

    def connect(self) -> None:
        try:
            self.session = Session(
                self.username,
                self.password,
                is_test=self.is_paper,
                remember_me=self.remember_me
            )
            logger.info(f"Connected to Tastytrade {'PAPER' if self.is_paper else 'LIVE'} environment.")

            accounts_list = Account.get_accounts(self.session)
            self.accounts = {acc.account_number: acc for acc in accounts_list}
            logger.info(f"Loaded {len(self.accounts)} account(s).")

        except Exception as e:
            logger.error(f"Tastytrade connection failed: {e}")
            raise

    def _get_account(self, account_id: Optional[str]) -> Account:
        if not account_id:
            account_id = next(iter(self.accounts))
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found.")
        return self.accounts[account_id]

    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.session:
            raise RuntimeError("Broker not connected.")
        account = self._get_account(account_id)
        positions = account.get_positions(self.session)
        return [
            {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "entry_price": float(pos.average_price or 0),
                "current_price": float(pos.mark_price or 0),
                "greeks": pos.greeks.to_dict() if hasattr(pos, 'greeks') and pos.greeks else {}
            }
            for pos in positions
        ]

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict:
        if not self.session:
            raise RuntimeError("Broker not connected.")
        account = self._get_account(account_id)
        balances = account.get_balances(self.session)
        return {
            "cash_balance": float(balances.cash_balance or 0),
            "buying_power": float(balances.buying_power or 0),
            "equity": float(balances.equity or 0)
        }

    def execute_order(self, order: NeutralOrder, account_id: Optional[str] = None) -> Dict:
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

            # Credit orders have positive price, debit negative
            if tt_order.price is not None:
                tt_order.price = abs(tt_order.price) if order.price_effect == PriceEffect.CREDIT else -abs(tt_order.price)

            response = account.place_order(self.session, tt_order)
            logger.info(f"Order placed on {account.account_number}")
            return {"status": "success", "details": str(response)}

        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"status": "failed", "error": str(e)}