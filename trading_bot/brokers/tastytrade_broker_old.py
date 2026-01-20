# trading_bot/brokers/tastytrade_broker.py
"""Tastytrade broker implementation using the latest tastytrade SDK (tastyware/tastytrade)."""

from typing import List, Optional, Dict, Any
from decimal import Decimal

from tastytrade import Session  # Latest SDK uses Session directly
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect
from tastytrade.instruments import get_option_chain
from trading_bot.detailed_position import DetailedPosition
from trading_bot.order_model import UniversalOrder, OrderLeg
from trading_bot.brokers.abstract_broker import Broker  # If you have abstract_broker.py
import logging
import asyncio
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Greeks
from tastytrade.instruments import get_option_chain
from tastytrade.utils import get_tasty_monthly


from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Greeks
from tastytrade.instruments import get_option_chain
from tastytrade.utils import get_tasty_monthly


logger = logging.getLogger(_name_)
class TastytradeBroker:
    def _init_(self, client_secret: str, refresh_token: str, is_paper: bool = True):
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.is_paper = is_paper
        self.session: Optional[Session] = None
        self.accounts: Dict[str, Account] = {}

    def connect(self):
        try:
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

    def _get_account(self, account_id: Optional[str]) -> Account:
        if not account_id:
            account_id = next(iter(self.accounts))
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found.")
        return self.accounts[account_id]

    def get_positions_without_greeks(self, account_id: Optional[str] = None) -> List[Dict]:
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
    
    async def stream_greeks(self, underlying="QQQ"):
    # 1) Get option chain and choose an expiry
     chain = get_option_chain(self.session, underlying)
     exp = get_tasty_monthly()  # or pick your own expiry date
     options = chain[exp]

    # 2) Pick one option and get its streamer symbol
     opt = options[0]
     symbol = opt.streamer_symbol  # e.g. ".QQQ260106C620"
     print("Subscribing Greeks for:", symbol)

    # 3) Subscribe to Greeks stream
     async with DXLinkStreamer(self.session) as streamer:
        await streamer.subscribe(Greeks, [symbol])

        # Fetch one Greeks snapshot
        greeks = await streamer.get_event(Greeks)
        print(greeks)

        # Access fields
        print("Delta:", greeks.delta)
        print("Gamma:", greeks.gamma)
        print("Theta:", greeks.theta)
        print("Vega:", greeks.vega)
        print("Rho:", greeks.rho)
        print("IV:", greeks.volatility)
    
    async def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        """REST positions + async Greeks enrichment."""
        if not self.session:
            raise RuntimeError("Broker not connected.")
        
        account = self._get_account(account_id)
        positions = account.get_positions(self.session)
        
        if not positions:
            return []
        
      # Build streamer map from chain
        streamer_map = {}
        for underlying in set(p.underlying_symbol for p in positions):
            chain = get_option_chain(self.session, underlying)
            for exp, opts in chain.items():
                for opt in opts:
                    streamer_map[opt.symbol.strip()] = opt.streamer_symbol
        
        # Build positions + streamers
        position_list = []
        streamer_symbols = []
        for pos in positions:
            symbol = pos.symbol.strip()
            streamer = streamer_map.get(symbol)
            if streamer:
                streamer_symbols.append(streamer)
                position_list.append({
                    "symbol": symbol,
                    "streamer_symbol": streamer,
                    "quantity": float(pos.quantity),
                    "entry_price": float(pos.average_open_price or 0),
                    "current_price": float(pos.mark_price or 0),
                    "greeks": {}
                })
        
        logger.info(f"Streaming {len(streamer_symbols)} symbols")
    
        # Greeks
        greeks_map = {}
        if streamer_symbols:
            async with DXLinkStreamer(self.session) as streamer:
                await streamer.subscribe(Greeks, streamer_symbols)
                for i, expected_sym in enumerate(streamer_symbols):
                    try:
                        g = await asyncio.wait_for(streamer.get_event(Greeks), timeout=5.0)
                        greeks_map[g.event_symbol] = g
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout {i}/{len(streamer_symbols)}")
                        break
        
        # Attach
        for pos in position_list:
            g = greeks_map.get(pos["streamer_symbol"])
            if g:
               pos["greeks"] = {
    "delta": round(float(g.delta), 2),
    "gamma": round(float(g.gamma), 4),   # often very small, use 4 if you prefer
    "theta": round(float(g.theta), 2),
    "vega":  round(float(g.vega), 2),
    "rho":   round(float(g.rho), 2),
    "iv":    round(float(g.volatility), 2),
}
    
        logger.info(f"Positions with Greeks: {sum(1 for p in position_list if p['greeks'])}/{len(position_list)}")
        return position_list
       

async def enrich_positions_for_detailed_sheet(broker, positions):
    """Convert tastytrade positions → DetailedPosition objects."""
    detailed = []
    
    for i, pos in enumerate(positions):
        # Parse symbol
        sym = pos["symbol"].strip()
        underlying = sym[:3]  # QQQ, AAPL, etc.
        option_type = "Call" if "C" in sym else "Put"
        
        # Extract strike from symbol (e.g., QQQ260106C00620000 → 620.00)
        strike = float(sym[-8:]) / 1000
        
        # Extract expiry (YYMMDD → 2026-01-06)
        from datetime import datetime
        expiry_str = sym[3:9]  # "260106"
        expiry = datetime.strptime(expiry_str, "%y%m%d").date()
        
        d_pos = DetailedPosition(
            symbol=sym,
            underlying=underlying,
            option_type=option_type,
            strike=strike,
            expiry_date=expiry,
            quantity=pos["quantity"],
            entry_premium=pos["entry_price"],
            entry_greeks=pos["greeks"],
            trade_id="Trade001",  # Set from your order tracking
            leg_id=f"Leg{i+1}"
        )
        
        # Update with current Greeks
        d_pos.update_current_price(pos["current_price"], pos["greeks"])
        detailed.append(d_pos)
    
    return detailed
# trading_bot/brokers/tastytrade_broker.py
"""Tastytrade broker implementation using the latest tastytrade SDK (tastyware/tastytrade)."""

from typing import List, Optional, Dict, Any
from decimal import Decimal

from tastytrade import Session  # Latest SDK uses Session directly
from tastytrade.account import Account
from tastytrade.instruments import Option
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect
from tastytrade.instruments import get_option_chain
from trading_bot.detailed_position import DetailedPosition
from trading_bot.order_model import UniversalOrder, OrderLeg
from trading_bot.brokers.abstract_broker import Broker  # If you have abstract_broker.py
import logging

logger = logging.getLogger(_name_)
class TastytradeBroker:
    def _init_(self, client_secret: str, refresh_token: str, is_paper: bool = True):
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.is_paper = is_paper
        self.session: Optional[Session] = None
        self.accounts: Dict[str, Account] = {}

    def connect(self):
        try:
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

    def _get_account(self, account_id: Optional[str]) -> Account:
        if not account_id:
            account_id = next(iter(self.accounts))
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found.")
        return self.accounts[account_id]

    def get_positions_without_greeks(self, account_id: Optional[str] = None) -> List[Dict]:
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
    
    async def stream_greeks(self, underlying="QQQ"):
    # 1) Get option chain and choose an expiry
     chain = get_option_chain(self.session, underlying)
     exp = get_tasty_monthly()  # or pick your own expiry date
     options = chain[exp]

    # 2) Pick one option and get its streamer symbol
     opt = options[0]
     symbol = opt.streamer_symbol  # e.g. ".QQQ260106C620"
     print("Subscribing Greeks for:", symbol)

    # 3) Subscribe to Greeks stream
     async with DXLinkStreamer(self.session) as streamer:
        await streamer.subscribe(Greeks, [symbol])

        # Fetch one Greeks snapshot
        greeks = await streamer.get_event(Greeks)
        print(greeks)

        # Access fields
        print("Delta:", greeks.delta)
        print("Gamma:", greeks.gamma)
        print("Theta:", greeks.theta)
        print("Vega:", greeks.vega)
        print("Rho:", greeks.rho)
        print("IV:", greeks.volatility)
    
    async def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        """REST positions + async Greeks enrichment."""
        if not self.session:
            raise RuntimeError("Broker not connected.")
        
        account = self._get_account(account_id)
        positions = account.get_positions(self.session)
        
        if not positions:
            return []
        
      # Build streamer map from chain
        streamer_map = {}
        for underlying in set(p.underlying_symbol for p in positions):
            chain = get_option_chain(self.session, underlying)
            for exp, opts in chain.items():
                for opt in opts:
                    streamer_map[opt.symbol.strip()] = opt.streamer_symbol
        
        # Build positions + streamers
        position_list = []
        streamer_symbols = []
        for pos in positions:
            symbol = pos.symbol.strip()
            streamer = streamer_map.get(symbol)
            if streamer:
                streamer_symbols.append(streamer)
                position_list.append({
                    "symbol": symbol,
                    "streamer_symbol": streamer,
                    "quantity": float(pos.quantity),
                    "entry_price": float(pos.average_open_price or 0),
                    "current_price": float(pos.mark_price or 0),
                    "greeks": {}
                })
        
        logger.info(f"Streaming {len(streamer_symbols)} symbols")
    
        # Greeks
        greeks_map = {}
        if streamer_symbols:
            async with DXLinkStreamer(self.session) as streamer:
                await streamer.subscribe(Greeks, streamer_symbols)
                for i, expected_sym in enumerate(streamer_symbols):
                    try:
                        g = await asyncio.wait_for(streamer.get_event(Greeks), timeout=5.0)
                        greeks_map[g.event_symbol] = g
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout {i}/{len(streamer_symbols)}")
                        break
        
        # Attach
        for pos in position_list:
            g = greeks_map.get(pos["streamer_symbol"])
            if g:
               pos["greeks"] = {
                    "delta": round(float(g.delta), 2),
                    "gamma": round(float(g.gamma), 4),   # often very small, use 4 if you prefer
                    "theta": round(float(g.theta), 2),
                    "vega":  round(float(g.vega), 2),
                    "rho":   round(float(g.rho), 2),
                    "iv":    round(float(g.volatility), 2),
                }
    
        logger.info(f"Positions with Greeks: {sum(1 for p in position_list if p['greeks'])}/{len(position_list)}")
        return position_list
       

async def enrich_positions_for_detailed_sheet(broker, positions):
    """Convert tastytrade positions → DetailedPosition objects."""
    detailed = []
    
    for i, pos in enumerate(positions):
        # Parse symbol
        sym = pos["symbol"].strip()
        underlying = sym[:3]  # QQQ, AAPL, etc.
        option_type = "Call" if "C" in sym else "Put"
        
        # Extract strike from symbol (e.g., QQQ260106C00620000 → 620.00)
        strike = float(sym[-8:]) / 1000
        
        # Extract expiry (YYMMDD → 2026-01-06)
        from datetime import datetime
        expiry_str = sym[3:9]  # "260106"
        expiry = datetime.strptime(expiry_str, "%y%m%d").date()
        
        d_pos = DetailedPosition(
            symbol=sym,
            underlying=underlying,
            option_type=option_type,
            strike=strike,
            expiry_date=expiry,
            quantity=pos["quantity"],
            entry_premium=pos["entry_price"],
            entry_greeks=pos["greeks"],
            trade_id="Trade001",  # Set from your order tracking
            leg_id=f"Leg{i+1}"
        )
        
        # Update with current Greeks
        d_pos.update_current_price(pos["current_price"], pos["greeks"])
        detailed.append(d_pos)
    
    return detailed
