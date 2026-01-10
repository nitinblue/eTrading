# trading_bot/brokers/tastytrade_broker.py
"""Tastytrade broker implementation using the latest tastytrade SDK (tastyware/tastytrade)."""

from typing import List, Optional, Dict, Any
from decimal import Decimal

from tastytrade import Session  # Latest SDK uses Session directly
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect

from trading_bot.order_model import UniversalOrder, OrderLeg
from trading_bot.brokers.abstract_broker import Broker  # If you have abstract_broker.py
import logging

logger = logging.getLogger(__name__)

# trading_bot/brokers/tastytrade_broker.py
"""
Tastytrade broker using OAuth2 (JWT) tokens — latest SDK compatible.
"""
from tastytrade import Session
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect
from decimal import Decimal
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class TastytradeBroker:
    def __init__(self, client_secret: str, refresh_token: str, is_paper: bool = True):
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.is_paper = is_paper
        self.session: Optional[Session] = None
        self.accounts: Dict[str, Account] = {}
        logging.info(f"Initializing in is_paper: {is_paper} mode")
        # Connect immediately on creation
        self.connect()

    def connect(self):
        try:
            logger.info(f"Just before connecting self.client_secret: {self.client_secret} self.refresh_token: {self.refresh_token} {'PAPER' if self.is_paper else 'LIVE'} via OAuth2")

            # Latest SDK: positional arguments
            self.session = Session(self.client_secret, self.refresh_token, is_test=self.is_paper)
            logger.info(f"Connected to Tastytrade {'PAPER' if self.is_paper else 'LIVE'} via OAuth2")
            # accounts_list = Account.get_accounts(self.session)
            accounts_list = Account.get(self.session)
            self.accounts = {acc.account_number: acc for acc in accounts_list}
            logger.info(f"Loaded {len(self.accounts)} account(s)")
        except Exception as e:
            logger.error(f"Tastytrade OAuth2 connection failed: {e}")
            raise
    def get_default_account(self) -> Optional[Account]:
            """Get default or first account."""
            if not self.accounts:
                logger.warning("No accounts loaded")
                return None
            return list(self.accounts.values())[0]
        
    def _get_account_old(self, account_id: Optional[str]) -> Account:
        if not account_id:
            account_id = next(iter(self.accounts))
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found.")
        return self.accounts[account_id]
    
    def _get_account(self, account_number: str = None) -> Optional[Account]:
        """Get account object (default to first one)."""
        if account_number:
            return self.accounts.get(account_number)
        return self.get_default_account() if self.accounts else None

    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.session:
            raise RuntimeError("Broker not connected.")
        account = self._get_account(account_id)
        positions = account.get_positions(self.session)
        return [
            {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "entry_price": float(pos.average_open_price or 0),
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
            "equity_buying_power": float(balances.equity_buying_power or 0),
            "margin_equity": float(balances.margin_equity or 0)
        }
        
    def get_realized_pnl(self, period: str = 'day',  account_id: Optional[str] = None) -> float:
        """
        Get realized PNL for a specific period.
        - period: 'day', 'month', 'ytd', 'total' (or any supported key)
        - Returns float
        """
        account = self._get_account(account_id)
        if not account:
            return 0.0

        try:
            balances = account.get_balances(self.session)
            if not balances:
                logger.warning("No balance data available")
                return 0.0

            key_mapping = {
                'day': 'realized_day_pnl',
                'month': 'realized_month_pnl',
                'ytd': 'realized_ytd_pnl',
                'total': 'realized_total_pnl'  # May not exist — check docs
            }

            key = key_mapping.get(period.lower(), 'realized_day_pnl')
            realized = float(balances.get(key, 0.0))

            logger.info(f"Realized PNL ({period}) for {account.account_number}: ${realized:.2f}")
            return realized

        except Exception as e:
            logger.error(f"Failed to get realized PNL ({period}): {e}")
            return 0.0
        
    def get_unrealized_pnl(self, account_id: Optional[str] = None) -> float:
        """
        Get total unrealized PNL from all open positions.
        - Returns float (positive = profit, negative = loss)
        - Use account_number to specify; defaults to first account
        """
        account = self._get_account(account_id)
        if not account:
            logger.warning("No account available for unrealized PNL")
            return 0.0

        try:
            positions = account.get_positions(self.session)
            if not positions or 'items' not in positions:
                logger.info("No open positions found")
                return 0.0

            total_unrealized = 0.0
            for pos in positions['items']:
                # Unrealized PNL is usually in 'unrealized_pnl' or 'mark_to_market'
                unrealized = float(pos.get('unrealized_pnl', 0.0))
                total_unrealized += unrealized

            logger.info(f"Unrealized PNL for {account.account_number}: ${total_unrealized:.2f}")
            return total_unrealized

        except Exception as e:
            logger.error(f"Failed to get unrealized PNL: {e}")
            return 0.0
    
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
                logger.info(f"Leg: {leg.symbol.strip()}")
                # instrument = Option.get_option(self.session, "MSFT  260116P00410000")
                # legs.append(instrument.build_leg(Decimal(leg.quantity), getattr(OrderAction, leg.action.value)))

            tt_order = NewOrder(
                time_in_force=getattr(OrderTimeInForce, order.time_in_force),
                order_type=getattr(OrderType, order.order_type.value),
                legs=order.legs,
                price=Decimal(str(order.limit_price)) if order.limit_price else None
            )
            logger.info(f"TT Order before price effect adjustment: {tt_order}")

            if tt_order.price is not None:
                tt_order.price = abs(tt_order.price) if order.price_effect == PriceEffect.CREDIT else -abs(tt_order.price)

            response = account.place_order(self.session, tt_order,order.dry_run)
            logger.info(f"Order placed on {account.account_number}")
            return {"status": "success", "details": str(response)}
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"status": "failed", "error": str(e)}
        
    def get_all_orders(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.session:
            raise RuntimeError("Broker not connected.")
        account = self._get_account(account_id)
        orders = account.get_live_orders(self.session)
        logger.info(f"Fetched {len(orders)} orders from account {account.account_number}{orders[0] if orders else ''}")
        return [
            {
                "order_id": order.id,
                "status": order.status,
                "symbol": order.underlying_symbol,
                # "quantity": order.quantity,
                # "filled_quantity": order.filled_quantity,
                "price": float(order.price or 0),
                "order_type": order.order_type,
                "price_effect": order.price,
                "legs": [
                    {
                        "symbol": leg.symbol,
                        "quantity": leg.quantity,
                        "action": leg.action
                    }
                    for leg in order.legs
                ],
                "time_in_force": order.time_in_force,
                "updated_at": order.updated_at.isoformat(),

            }
            for order in orders
        ]