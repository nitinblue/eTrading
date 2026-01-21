"""
Tastytrade Broker Adapter - Fixed version with proper Greeks and no duplicates
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging
import yaml
from pathlib import Path

from tastytrade import Session, Account
from tastytrade.instruments import Equity, Option
import os
import re
#from adapters.base import BrokerAdapter
import core.models.domain as dm

logger = logging.getLogger(__name__)

# ============================================================================
# Base Adapter Interface
# ============================================================================

class BrokerAdapter:
    """Base class for broker adapters"""
    
    def __init__(self, account_id: str, credentials: str):
        self.account_id = account_id
        self.credentials = credentials
    
    def authenticate(self) -> bool:
        raise NotImplementedError
    
    def get_account_balance(self) -> Dict[str, Decimal]:
        raise NotImplementedError
    
    def get_positions(self) -> List[dm.Position]:
        raise NotImplementedError
    
    def get_orders(self, status: Optional[str] = None) -> List[dm.Order]:
        raise NotImplementedError
    
    def get_trades(self, start_date: Optional[datetime] = None) -> List[dm.Trade]:
        raise NotImplementedError
    
    def submit_order(self, order: dm.Order) -> str:
        raise NotImplementedError
    
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        raise NotImplementedError
    
    def get_option_chain(self, underlying: str, expiration: Optional[datetime] = None) -> List[dm.Symbol]:
        raise NotImplementedError

class TastytradeAdapter(BrokerAdapter):
    """Tastytrade broker integration"""
    
    def __init__(self, account_number: str = None, is_paper: bool = False):
        """
        Initialize Tastytrade adapter
        
        Args:
            account_number: Specific account number (optional, will use first if not provided)
            is_paper: Whether to use paper trading account
        """
        tastytrade_credential_file = "tastytrade_broker.yaml"
        super().__init__(account_number or "", tastytrade_credential_file)
        
        self.is_paper = is_paper
        self.session = None
        self.account = None
        self.accounts = {}
        self._account_number = account_number
        self._dxlink_streamer = None
        
        # Load credentials from YAML (which references .env)
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from YAML file (which may reference environment variables)"""
        try:
            # Look for YAML file in multiple locations
            possible_paths = [
                Path(self.credentials),  # Current directory
                Path(__file__).parent / self.credentials,  # adapters/ folder
                Path(__file__).parent.parent / self.credentials,  # trading_cotrader/ folder
                Path(__file__).parent.parent.parent / self.credentials,  # Parent of trading_cotrader
            ]
            
            cred_path = None
            for path in possible_paths:
                if path.exists():
                    cred_path = path
                    logger.info(f"Found credentials file at: {path.absolute()}")
                    break
            
            if not cred_path:
                raise FileNotFoundError(
                    f"Credentials file '{self.credentials}' not found. "
                    f"Tried locations: {[str(p) for p in possible_paths]}"
                )
            
            logger.info(f"Loading credentials from: {cred_path}")
            
            with open(cred_path, 'r') as f:
                creds = yaml.safe_load(f)
            
            logger.info("creds value: {creds['live']}")
            mode = 'paper' if self.is_paper else 'live'
            
            # Get credentials - they may be direct values or env var references
            mode_secret = creds["broker"][mode]['client_secret']
            mode_token = creds["broker"][mode]['refresh_token']
            self.client_secret = self._resolve_credential(mode_secret)
            self.refresh_token = self._resolve_credential(mode_token)
            
            #self.client_secret = self._resolve_credential(creds[mode]['client_secret'])
            #self.refresh_token = self._resolve_credential(creds[mode]['refresh_token'])
            
            logger.info(f"✓ Loaded credentials for {mode} mode (secret length: {len(self.client_secret)})")
            
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            raise

    def _resolve_credential(self, value: str) -> str:
        """
        Resolve credential value - either direct value or environment variable
        
        Supports:
        - Direct value: "abc123"
        - Env var: "${TASTYTRADE_CLIENT_SECRET}"
        - Env var: "$TASTYTRADE_CLIENT_SECRET"
        """

        
        if not value:
            return value
        
        # Check if it's an environment variable reference
        # Matches: ${VAR_NAME} or $VAR_NAME
        env_pattern = r'\$\{?([A-Z_]+)\}?'
        match = re.match(env_pattern, value)
        
        if match:
            env_var = match.group(1)
            resolved = os.getenv(env_var)
            if not resolved:
                raise ValueError(f"Environment variable {env_var} not found")
            return resolved
        
        # Direct value
        return value
    
    def authenticate(self) -> bool:
        """Authenticate with Tastytrade"""
        try:
            logger.info(f"Connecting to Tastytrade | {'PAPER' if self.is_paper else 'LIVE'}")
            
            # Create session
            self.session = Session(
                self.client_secret,
                self.refresh_token,
                is_test=self.is_paper
            )
            
            # Get accounts
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
            
            logger.info("✓ Authenticated successfully with Tastytrade")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.exception("Full error:")
            return False
    
    def get_account_balance(self) -> Dict[str, Decimal]:
        """Get account balances"""
        try:
            if not self.account:
                raise ValueError("Not authenticated")
            
            balance_data = self.account.get_balances(self.session)
            
            return {
                'cash_balance': Decimal(str(balance_data.cash_balance or 0)),
                'buying_power': Decimal(str(balance_data.derivative_buying_power or 0)),
                'net_liquidating_value': Decimal(str(balance_data.net_liquidating_value or 0)),
                'maintenance_excess': Decimal(str(balance_data.maintenance_excess or 0)),
                'equity_buying_power': Decimal(str(balance_data.equity_buying_power or 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {}
    
    def get_positions(self) -> List[dm.Position]:
        """
        Fetch positions from Tastytrade with proper Greeks
        
        CRITICAL FIXES:
        1. Quantity is SIGNED (positive = long, negative = short)
        2. Greeks are PER CONTRACT, need to multiply by quantity
        3. Broker position ID for uniqueness
        """
        try:
            if not self.account:
                raise ValueError("Not authenticated")
            
            positions_data = self.account.get_positions(self.session)
            positions = []
            
            logger.info(f"Fetching positions from Tastytrade...")
            
            for pos_data in positions_data:
                try:
                    # Parse symbol
                    symbol = self._parse_symbol_from_position(pos_data)
                    
                    # CRITICAL: Quantity is signed!
                    # Positive = Long, Negative = Short
                    raw_quantity = int(pos_data.quantity or 0)
                    
                    # Additional check with quantity_direction if available
                    if hasattr(pos_data, 'quantity_direction'):
                        if pos_data.quantity_direction == 'Short':
                            raw_quantity = -abs(raw_quantity)
                        else:
                            raw_quantity = abs(raw_quantity)
                    
                    # Skip zero quantity
                    if raw_quantity == 0:
                        logger.debug(f"Skipping {symbol.ticker} - zero quantity")
                        continue
                    
                    # Get broker position ID (critical for preventing duplicates)
                    broker_pos_id = str(pos_data.id) if hasattr(pos_data, 'id') else None
                    if not broker_pos_id:
                        # Fallback: generate from symbol
                        broker_pos_id = f"{self.account_id}_{symbol.get_option_symbol() if symbol.asset_type == dm.AssetType.OPTION else symbol.ticker}"
                    
                    # Create position
                    position = dm.Position(
                        symbol=symbol,
                        quantity=raw_quantity,  # Keep the sign!
                        average_price=Decimal(str(pos_data.average_open_price or 0)),
                        current_price=Decimal(str(pos_data.close_price or 0)),
                        market_value=Decimal(str(pos_data.mark_price or 0)),
                        total_cost=Decimal(str(abs(pos_data.average_open_price or 0))) * abs(raw_quantity) * symbol.multiplier,
                        broker_position_id=broker_pos_id,
                    )
                    
                    # CRITICAL: Get Greeks from Tastytrade
                    if hasattr(pos_data, 'greeks') and pos_data.greeks:
                        greeks = pos_data.greeks
                        
                        # Tastytrade Greeks are PER CONTRACT
                        # Need to multiply by quantity for POSITION-LEVEL Greeks
                        position.greeks = dm.Greeks(
                            delta=Decimal(str(greeks.delta or 0)) * abs(raw_quantity),
                            gamma=Decimal(str(greeks.gamma or 0)) * abs(raw_quantity),
                            theta=Decimal(str(greeks.theta or 0)) * abs(raw_quantity),
                            vega=Decimal(str(greeks.vega or 0)) * abs(raw_quantity),
                            rho=Decimal(str(greeks.rho or 0)) * abs(raw_quantity) if hasattr(greeks, 'rho') else Decimal('0'),
                            timestamp=datetime.utcnow()
                        )
                        
                        logger.debug(f"Position {symbol.ticker}: qty={raw_quantity}, Δ={position.greeks.delta:.2f}")
                    else:
                        # No Greeks available (equity positions)
                        if symbol.asset_type == dm.AssetType.EQUITY:
                            # Stock delta = 1 per share
                            position.greeks = dm.Greeks(
                                delta=Decimal(str(raw_quantity)),
                                timestamp=datetime.utcnow()
                            )
                    
                    positions.append(position)
                    
                except Exception as e:
                    logger.warning(f"Skipping position due to error: {e}")
                    logger.exception("Position parse error:")
                    continue
            
            logger.info(f"✓ Fetched {len(positions)} positions with Greeks")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            logger.exception("Full error:")
            return []
    
    def get_orders(self, status: Optional[str] = None) -> List[dm.Order]:
        """Fetch orders from Tastytrade"""
        try:
            if not self.account:
                raise ValueError("Not authenticated")
            
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
            
            logger.info(f"✓ Fetched {len(orders)} orders")
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_trades(self, start_date: Optional[datetime] = None) -> List[dm.Trade]:
        """Fetch trade history (not implemented yet)"""
        logger.warning("get_trades not yet implemented")
        return []
    
    def submit_order(self, order: dm.Order) -> str:
        """Submit order (not implemented yet)"""
        logger.warning("submit_order not yet implemented")
        raise NotImplementedError("Order submission coming in Days 5-6")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order (not implemented yet)"""
        logger.warning("cancel_order not yet implemented")
        return False
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get quote for a symbol"""
        logger.warning("get_quote not yet implemented")
        return {}
    
    def get_option_chain(self, underlying: str, expiration: Optional[datetime] = None) -> List[dm.Symbol]:
        """Get option chain"""
        logger.warning("get_option_chain not yet implemented")
        return []
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _parse_symbol_from_position(self, pos_data) -> dm.Symbol:
        """Parse symbol from position data"""
        try:
            instrument_type = pos_data.instrument_type
            symbol_str = pos_data.symbol
            
            if instrument_type == 'Equity':
                return dm.Symbol(
                    ticker=symbol_str,
                    asset_type=dm.AssetType.EQUITY,
                    multiplier=1
                )
            elif instrument_type == 'Equity Option':
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
                logger.warning(f"Unknown instrument type: {instrument_type}, defaulting to equity")
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
            # Return basic equity symbol as fallback
            ticker = symbol_str[:6].strip() if len(symbol_str) >= 6 else symbol_str
            return dm.Symbol(
                ticker=ticker,
                asset_type=dm.AssetType.EQUITY,
                multiplier=1
            )
    
    def _parse_order(self, order_data) -> dm.Order:
        """Parse Tastytrade order (simplified for now)"""
        # Will implement fully in Days 5-6
        return dm.Order(
            broker_order_id=str(order_data.id) if hasattr(order_data, 'id') else None,
            status=dm.OrderStatus.OPEN
        )


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