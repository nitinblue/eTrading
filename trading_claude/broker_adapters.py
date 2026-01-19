# ============================================================================
# BROKER ADAPTER INTERFACE
# ============================================================================

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
import logging
import os

import data_model as dm
from config_loader import load_yaml_with_env

# Import from core models (previous artifact)
# from core_models import Portfolio, Trade, Position, Order, Symbol, Leg, AssetType, OptionType, OrderSide, OrderStatus, OrderType

logger = logging.getLogger(__name__)


class BrokerAdapter(ABC):
    """Abstract base class for broker integrations"""
    
    def __init__(self, account_id: str, credential_file: str):
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        broker_cfg_path = os.path.join(base_dir,credential_file)

        cfg = load_yaml_with_env(broker_cfg_path)
    
        mode = cfg["general"]["execution_mode"]  # live / paper
        is_paper = cfg["general"]["is_paper"]

        broker_cfg = cfg["broker"][mode]
        
        self.account_id = account_id
        self.client_secret = broker_cfg["client_secret"]
        self.refresh_token = broker_cfg["refresh_token"]
        self.is_paper = is_paper
        
        self._authenticated = False
        

    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with broker API"""
        pass
    
    @abstractmethod
    def get_account_balance(self) -> Dict[str, Decimal]:
        """Get account cash balance and buying power"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[dm.Position]:
        """Fetch all current positions"""
        pass
    
    @abstractmethod
    def get_orders(self, status: Optional[str] = None) -> List[dm.Order]:
        """Fetch orders, optionally filtered by status"""
        pass
    
    @abstractmethod
    def get_trades(self, start_date: Optional[datetime] = None) -> List[dm.Trade]:
        """Fetch trade history"""
        pass
    
    @abstractmethod
    def submit_order(self, order: dm.Order) -> str:
        """Submit an order and return broker order ID"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        pass
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for a symbol"""
        pass
    
    @abstractmethod
    def get_option_chain(self, underlying: str, expiration: Optional[datetime] = None) -> List[dm.Symbol]:
        """Get option chain for an underlying"""
        pass


# ============================================================================
# TASTYTRADE ADAPTER IMPLEMENTATION
# ============================================================================

from tastytrade import Session, Account
#from tastytrade.dxfeed import EventType
from tastytrade.instruments import Equity, Option, Future, Cryptocurrency
import uuid


class TastytradeAdapter(BrokerAdapter):
    """Tastytrade broker integration using client_secret and refresh_token"""
    
    def __init__(self, account_number: str = None, is_paper: bool = False):
        """
        Initialize Tastytrade adapter
        
        Args:
            client_secret: Tastytrade client secret
            refresh_token: Tastytrade refresh token
            account_number: Specific account number to use (optional, will use first if not provided)
            is_paper: Whether to use paper trading account
        """
        
        tastytrade_credential_file = "Tastytrade_broker.yaml"
        super().__init__(account_number or "",tastytrade_credential_file)
        
        self.is_paper = is_paper
        self.session = None
        self.account = None
        self.accounts = {}
        self._account_number = account_number

    def authenticate(self) -> bool:
        """Authenticate with Tastytrade API using refresh token"""
        try:
            logger.info(
                f"Connecting to Tastytrade | {'PAPER' if self.is_paper else 'LIVE'}"
            )
            
            # Create session using client_secret and refresh_token
            self.session = Session(
                self.client_secret,
                self.refresh_token,
                is_test=self.is_paper
            )
            
            # Get all accounts
            accounts = Account.get(self.session)
            self.accounts = {a.account_number: a for a in accounts}
            
            logger.info(f"Loaded {len(self.accounts)} account(s): {list(self.accounts.keys())}")
            
            # Select account
            if self._account_number:
                if self._account_number not in self.accounts:
                    raise ValueError(f"Account {self._account_number} not found")
                self.account = self.accounts[self._account_number]
                self.account_id = self._account_number
            else:
                # Use first account
                self.account = list(self.accounts.values())[0]
                self.account_id = self.account.account_number
                logger.info(f"Using account: {self.account_id}")
            
            self._authenticated = True
            logger.info("Authenticated successfully with Tastytrade")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.exception("Full error:")
            return False
    
    def get_account_balance(self) -> Dict[str, Decimal]:
        """Get account balances"""
        try:
            if not self.account:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Get current balance
            balance_data = self.account.get_balances(self.session)
            
            return {
                "cash_balance": Decimal(str(balance_data.cash_balance or 0)),
                "buying_power": Decimal(str(balance_data.derivative_buying_power or 0)),
                "net_liquidating_value": Decimal(str(balance_data.net_liquidating_value or 0)),
                "maintenance_excess": Decimal(str(balance_data.maintenance_excess or 0)),
                "equity_buying_power": Decimal(str(balance_data.equity_buying_power or 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            logger.exception("Full error:")
            return {}
    
    def get_positions(self) -> List[dm.Position]:
        """Fetch current positions from Tastytrade"""
        try:
            if not self.account:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Get positions from API
            positions_data = self.account.get_positions(self.session)
            positions = []
            
            for pos_data in positions_data:
                try:
                    # Parse symbol
                    symbol = self._parse_symbol_from_position(pos_data)
                    
                    # Create position
                    position = dm.Position(
                        symbol=symbol,
                        quantity=int(pos_data.quantity or 0),
                        average_price=Decimal(str(pos_data.average_open_price or 0)),
                        current_price=Decimal(str(pos_data.close_price or 0)),
                        market_value=Decimal(str(pos_data.mark_price or 0)),
                        total_cost=Decimal(str(pos_data.average_open_price or 0)) * abs(int(pos_data.quantity or 0)) * symbol.multiplier,
                        broker_position_id=str(pos_data.id) if hasattr(pos_data, 'id') else None,
                    )
                    
                    # Add Greeks if available (for options)
                    if hasattr(pos_data, 'greeks') and pos_data.greeks:
                        position.delta = Decimal(str(pos_data.greeks.delta or 0))
                        position.gamma = Decimal(str(pos_data.greeks.gamma or 0))
                        position.theta = Decimal(str(pos_data.greeks.theta or 0))
                        position.vega = Decimal(str(pos_data.greeks.vega or 0))
                    
                    positions.append(position)
                    
                except Exception as e:
                    logger.warning(f"Skipping position due to error: {e}")
                    continue
            
            logger.info(f"Fetched {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            logger.exception("Full error:")
            return []
    
    def get_orders(self, status: Optional[str] = None) -> List[dm.Order]:
        """Fetch orders from Tastytrade"""
        try:
            if not self.account:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Get live orders
            orders_data = self.account.get_live_orders(self.session)
            orders = []
            
            for order_data in orders_data:
                try:
                    order = self._parse_order(order_data)
                    
                    # Filter by status if provided
                    if status and order.status.value != status.lower():
                        continue
                    
                    orders.append(order)
                    
                except Exception as e:
                    logger.warning(f"Skipping order due to error: {e}")
                    continue
            
            logger.info(f"Fetched {len(orders)} orders")
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            logger.exception("Full error:")
            return []
    
    def get_trades(self, start_date: Optional[datetime] = None) -> List[dm.Trade]:
        """Fetch trade history"""
        try:
            if not self.account:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Get transaction history
            transactions = self.account.get_transaction_history(
                self.session,
                start_date=start_date
            )
            
            # Group transactions into trades
            trades = self._group_transactions_into_trades(transactions)
            
            logger.info(f"Fetched {len(trades)} trades")
            return trades
            
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            logger.exception("Full error:")
            return []
    
    def submit_order(self, order: Order) -> str:
        """Submit order to Tastytrade"""
        try:
            if not self.account:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Build order using tastytrade library
            from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType as TTOrderType, PriceEffect
            
            # Map our order type to tastytrade order type
            order_type_map = {
                dm.OrderType.LIMIT: TTOrderType.LIMIT,
                dm.OrderType.MARKET: TTOrderType.MARKET,
                dm.OrderType.STOP: TTOrderType.STOP,
                dm.OrderType.STOP_LIMIT: TTOrderType.STOP_LIMIT
            }
            
            # Map time in force
            tif_map = {
                "DAY": OrderTimeInForce.DAY,
                "GTC": OrderTimeInForce.GTC,
                "GTD": OrderTimeInForce.GTD,
                "IOC": OrderTimeInForce.IOC
            }
            
            # Build legs
            from tastytrade.order import Leg as TTLeg
            tt_legs = []
            
            for leg in order.legs:
                # Determine action
                if leg.side == dm.OrderSide.BUY_TO_OPEN or leg.side == dm.OrderSide.BUY:
                    action = OrderAction.BUY_TO_OPEN
                elif leg.side == dm.OrderSide.SELL_TO_OPEN or leg.side == dm.OrderSide.SELL:
                    action = OrderAction.SELL_TO_OPEN
                elif leg.side == dm.OrderSide.BUY_TO_CLOSE:
                    action = OrderAction.BUY_TO_CLOSE
                elif leg.side == dm.OrderSide.SELL_TO_CLOSE:
                    action = OrderAction.SELL_TO_CLOSE
                else:
                    action = OrderAction.BUY_TO_OPEN
                
                # Get symbol string
                if leg.symbol.asset_type == dm.AssetType.OPTION:
                    symbol_str = leg.symbol.get_option_symbol()
                else:
                    symbol_str = leg.symbol.ticker
                
                tt_leg = TTLeg(
                    symbol=symbol_str,
                    quantity=abs(leg.quantity),
                    action=action
                )
                tt_legs.append(tt_leg)
            
            # Create order
            new_order = NewOrder(
                time_in_force=tif_map.get(order.time_in_force, OrderTimeInForce.DAY),
                order_type=order_type_map.get(order.order_type, TTOrderType.LIMIT),
                legs=tt_legs,
                price=float(order.limit_price) if order.limit_price else None,
                stop_trigger=float(order.stop_price) if order.stop_price else None
            )
            
            # Place order
            response = self.account.place_order(self.session, new_order, dry_run=False)
            
            # Get order ID from response
            if hasattr(response, 'order') and hasattr(response.order, 'id'):
                broker_order_id = str(response.order.id)
            elif hasattr(response, 'id'):
                broker_order_id = str(response.id)
            else:
                broker_order_id = str(uuid.uuid4())  # Fallback
            
            logger.info(f"Order submitted successfully: {broker_order_id}")
            return broker_order_id
            
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            logger.exception("Full error:")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            if not self.account:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Delete order
            self.account.delete_order(self.session, order_id)
            
            logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            logger.exception("Full error:")
            return False
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get quote for a symbol"""
        try:
            if not self.session:
                raise ValueError("Not authenticated - call authenticate() first")
            
            # Use the market data endpoint instead of DXLink
            from tastytrade.instruments import get_quantity_decimal_precisions
            
            # For now, return a placeholder
            # In production, you'd implement proper quote fetching
            logger.warning(f"Quote fetching not fully implemented for {symbol}")
            
            return {
                "symbol": symbol,
                "bid": Decimal("0"),
                "ask": Decimal("0"),
                "last": Decimal("0"),
                "mark": Decimal("0"),
                "volume": 0,
                "open_interest": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return {}
    
    def get_option_chain(self, underlying: str, expiration: Optional[datetime] = None) -> List[dm.Symbol]:
        """Get option chain"""
        try:
            if not self.session:
                raise ValueError("Not authenticated - call authenticate() first")
            
            from tastytrade.instruments import get_option_chain
            
            # Get option chain
            chain = get_option_chain(self.session, underlying)
            symbols = []
            
            for exp in chain.expirations:
                exp_date = datetime.strptime(exp.expiration_date, "%Y-%m-%d")
                
                # Filter by expiration if provided
                if expiration and exp_date.date() != expiration.date():
                    continue
                
                for strike in exp.strikes:
                    strike_price = Decimal(str(strike.strike_price))
                    
                    # Add call if exists
                    if strike.call:
                        symbols.append(dm.Symbol(
                            ticker=underlying,
                            asset_type=dm.AssetType.OPTION,
                            option_type=dm.OptionType.CALL,
                            strike=strike_price,
                            expiration=exp_date,
                            multiplier=100
                        ))
                    
                    # Add put if exists
                    if strike.put:
                        symbols.append(dm.Symbol(
                            ticker=underlying,
                            asset_type=dm.AssetType.OPTION,
                            option_type=dm.OptionType.PUT,
                            strike=strike_price,
                            expiration=exp_date,
                            multiplier=100
                        ))
            
            logger.info(f"Fetched {len(symbols)} option contracts")
            return symbols
            
        except Exception as e:
            logger.error(f"Failed to get option chain: {e}")
            logger.exception("Full error:")
            return []
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _parse_symbol_from_position(self, pos_data) -> dm.Symbol:
        """Parse symbol from position data"""
        try:
            # Get instrument type
            instrument_type = pos_data.instrument_type
            symbol_str = pos_data.symbol
            
            if instrument_type == 'Equity':
                return dm.Symbol(
                    ticker=symbol_str,
                    asset_type=dm.AssetType.EQUITY,
                    multiplier=1
                )
            elif instrument_type == 'Equity Option':
                # Parse OCC format option symbol
                return self._parse_occ_symbol(symbol_str)
            elif instrument_type == 'Future':
                return dm.Symbol(
                    ticker=symbol_str,
                    asset_type=dm.AssetType.FUTURE,
                    multiplier=1
                )
            elif instrument_type == 'Cryptocurrency':
                return dm.Symbol(
                    ticker=symbol_str,
                    asset_type=dm.AssetType.CRYPTO,
                    multiplier=1
                )
            else:
                # Default to equity
                return dm.Symbol(
                    ticker=symbol_str,
                    asset_type=dm.AssetType.EQUITY,
                    multiplier=1
                )
        except Exception as e:
            logger.warning(f"Error parsing symbol: {e}, defaulting to {symbol_str}")
            return dm.Symbol(
                ticker=symbol_str,
                asset_type=dm.AssetType.EQUITY,
                multiplier=1
            )
    
    def _parse_occ_symbol(self, symbol_str: str) -> dm.Symbol:
        """
        Parse OCC format option symbol
        Example: "AAPL  240119C00150000" = AAPL Jan 19, 2024 $150 Call
        """
        try:
            if len(symbol_str) < 21:
                raise ValueError(f"Invalid OCC symbol length: {symbol_str}")
            
            ticker = symbol_str[:6].strip()
            exp_str = symbol_str[6:12]
            opt_type_char = symbol_str[12]
            strike_str = symbol_str[13:21]
            
            expiration = datetime.strptime(exp_str, "%y%m%d")
            option_type = dm.OptionType.CALL if opt_type_char == 'C' else dm.OptionType.PUT
            strike = Decimal(strike_str) / 1000
            
            return dm.Symbol(
                ticker=ticker,
                asset_type=dm.AssetType.OPTION,
                option_type=option_type,
                strike=strike,
                expiration=expiration,
                multiplier=100
            )
        except Exception as e:
            logger.error(f"Failed to parse OCC symbol {symbol_str}: {e}")
            # Return a basic equity symbol as fallback
            return dm.Symbol(
                ticker=symbol_str[:6].strip() if len(symbol_str) >= 6 else symbol_str,
                asset_type=dm.AssetType.EQUITY,
                multiplier=1
            )
    
    def _parse_order(self, order_data) -> dm.Order:
        """Parse Tastytrade order into Order object"""
        # Parse legs
        legs = []
        for leg_data in order_data.legs:
            try:
                symbol = self._parse_occ_symbol(leg_data.symbol) if ' ' in leg_data.symbol else dm.Symbol(
                    ticker=leg_data.symbol,
                    asset_type=dm.AssetType.EQUITY,
                    multiplier=1
                )
                
                # Determine side from action
                action_str = str(leg_data.action)
                if 'BUY_TO_OPEN' in action_str:
                    side = dm.OrderSide.BUY_TO_OPEN
                elif 'SELL_TO_OPEN' in action_str:
                    side = dm.OrderSide.SELL_TO_OPEN
                elif 'BUY_TO_CLOSE' in action_str:
                    side = dm.OrderSide.BUY_TO_CLOSE
                elif 'SELL_TO_CLOSE' in action_str:
                    side = dm.OrderSide.SELL_TO_CLOSE
                else:
                    side = dm.OrderSide.BUY if 'BUY' in action_str else dm.OrderSide.SELL
                
                leg = dm.Leg(
                    symbol=symbol,
                    quantity=int(leg_data.quantity),
                    side=side,
                    broker_leg_id=str(getattr(leg_data, 'id', ''))
                )
                legs.append(leg)
            except Exception as e:
                logger.warning(f"Error parsing order leg: {e}")
                continue
        
        # Parse order status
        status_str = str(order_data.status).upper()
        status_map = {
            "RECEIVED": dm.OrderStatus.PENDING,
            "LIVE": dm.OrderStatus.OPEN,
            "FILLED": dm.OrderStatus.FILLED,
            "CANCELLED": dm.OrderStatus.CANCELLED,
            "CANCELED": dm.OrderStatus.CANCELLED,
            "REJECTED": dm.OrderStatus.REJECTED,
            "WORKING": dm.OrderStatus.OPEN,
            "PENDING": dm.OrderStatus.PENDING
        }
        status = status_map.get(status_str, dm.OrderStatus.PENDING)
        
        # Parse order type
        order_type_str = str(order_data.order_type).upper()
        order_type_map = {
            "LIMIT": dm.OrderType.LIMIT,
            "MARKET": dm.OrderType.MARKET,
            "STOP": dm.OrderType.STOP,
            "STOP_LIMIT": dm.OrderType.STOP_LIMIT,
            "STOPLIMIT": dm.OrderType.STOP_LIMIT
        }
        order_type = order_type_map.get(order_type_str, dm.OrderType.MARKET)
        
        order = dm.Order(
            legs=legs,
            order_type=order_type,
            status=status,
            broker_order_id=str(order_data.id),
            created_at=order_data.received_at if hasattr(order_data, 'received_at') else datetime.utcnow(),
            time_in_force=str(order_data.time_in_force) if hasattr(order_data, 'time_in_force') else "DAY"
        )
        
        # Add price info
        if hasattr(order_data, 'price') and order_data.price:
            order.limit_price = Decimal(str(order_data.price))
        
        if hasattr(order_data, 'stop_trigger') and order_data.stop_trigger:
            order.stop_price = Decimal(str(order_data.stop_trigger))
        
        return order
    
    def _group_transactions_into_trades(self, transactions: List) -> List[dm.Trade]:
        """Group individual transactions into logical trades"""
        trades = []
        trade_groups = {}
        
        for txn in transactions:
            try:
                # Only process trade transactions
                if not hasattr(txn, 'transaction_type') or txn.transaction_type not in ['Trade', 'Receive Deliver']:
                    continue
                
                # Group by date and underlying
                underlying = getattr(txn, 'underlying_symbol', '') or ''
                executed_at = getattr(txn, 'executed_at', datetime.utcnow())
                date = executed_at.strftime('%Y-%m-%d') if isinstance(executed_at, datetime) else str(executed_at)[:10]
                
                key = f"{underlying}_{date}"
                
                if key not in trade_groups:
                    trade_groups[key] = []
                
                trade_groups[key].append(txn)
            except Exception as e:
                logger.warning(f"Error processing transaction: {e}")
                continue
        
        # Convert groups to Trade objects
        for group_key, txns in trade_groups.items():
            try:
                legs = []
                
                for txn in txns:
                    symbol_str = getattr(txn, 'symbol', '')
                    symbol = self._parse_occ_symbol(symbol_str) if ' ' in symbol_str else Symbol(
                        ticker=symbol_str,
                        asset_type=dm.AssetType.EQUITY,
                        multiplier=1
                    )
                    
                    quantity = int(getattr(txn, 'quantity', 0))
                    action = getattr(txn, 'action', 'Buy')
                    
                    leg = Leg(
                        symbol=symbol,
                        quantity=quantity if 'Buy' in str(action) else -quantity,
                        side=OrderSide.BUY if 'Buy' in str(action) else OrderSide.SELL,
                        entry_price=Decimal(str(getattr(txn, 'price', 0))),
                        entry_time=getattr(txn, 'executed_at', datetime.utcnow()),
                        fees=Decimal(str(getattr(txn, 'regulatory_fees', 0) or 0)) + 
                             Decimal(str(getattr(txn, 'clearing_fees', 0) or 0))
                    )
                    legs.append(leg)
                
                if legs:
                    trade = Trade(
                        legs=legs,
                        underlying_symbol=txns[0].underlying_symbol if hasattr(txns[0], 'underlying_symbol') else '',
                        opened_at=txns[0].executed_at if hasattr(txns[0], 'executed_at') else datetime.utcnow()
                    )
                    trades.append(trade)
            except Exception as e:
                logger.warning(f"Error creating trade from group: {e}")
                continue
        
        return trades


# ============================================================================
# BROKER FACTORY
# ============================================================================

class BrokerFactory:
    """Factory to create broker adapters"""
    
    @staticmethod
    def create_adapter(broker_name: str, **kwargs) -> BrokerAdapter:
        """
        Create a broker adapter by name
        
        Args:
            broker_name: Name of broker ('tastytrade', etc.)
            **kwargs: Broker-specific credentials
            
        For Tastytrade:
            client_secret: str
            refresh_token: str
            account_number: str (optional)
            is_paper: bool (default False)
        """
        adapters = {
            "tastytrade": TastytradeAdapter,
            # Add more brokers here
        }
        
        adapter_class = adapters.get(broker_name.lower())
        if not adapter_class:
            raise ValueError(f"Unknown broker: {broker_name}")
        
        return adapter_class(**kwargs)


# ============================================================================
# EXAMPLE USAGE / TASTY TRADE CONFIGURATION-ABSTRACED INSIDE ADAPTER
# ============================================================================


def main():
    adapter = TastytradeAdapter()
    
    if adapter.authenticate():
        print(f"Connected to account: {adapter.account_id}")
        # Get account balance
        balance = adapter.get_account_balance()
        print(f"Cash Balance: ${balance.get('cash_balance', 0)}")
        
        # Get positions
        positions = adapter.get_positions()
        print(f"Found {len(positions)} positions")
        
        # Get orders
        orders = adapter.get_orders()
        print(f"Found {len(orders)} orders")


if __name__ == "__main__":
    main()