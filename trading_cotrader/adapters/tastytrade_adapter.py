"""
Tastytrade Broker Adapter - Fixed version with option chain Greeks

KEY FIX: Greeks are fetched via get_option_chain() which is more reliable
than DXLink streaming for batch fetches.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging
import yaml
from pathlib import Path
from collections import defaultdict

from tastytrade import Session, Account
from tastytrade.instruments import Equity, Option
from tastytrade import get_option_chain
import os
import re

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


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


class TastytradeAdapter(BrokerAdapter):
    """Tastytrade broker integration with option chain Greeks"""

    def __init__(self, account_number: str = None, is_paper: bool = False):
        tastytrade_credential_file = "tastytrade_broker.yaml"
        super().__init__(account_number or "", tastytrade_credential_file)

        self.is_paper = is_paper
        self.session = None
        self.account = None
        self.accounts = {}
        self._account_number = account_number

        # Load credentials
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from YAML file"""
        try:
            possible_paths = [
                Path(self.credentials),
                Path(__file__).parent / self.credentials,
                Path(__file__).parent.parent / self.credentials,
                Path(__file__).parent.parent.parent / self.credentials,
            ]

            cred_path = None
            for path in possible_paths:
                if path.exists():
                    cred_path = path
                    logger.info(f"Found credentials file at: {path.absolute()}")
                    break

            if not cred_path:
                raise FileNotFoundError(f"Credentials file '{self.credentials}' not found")

            logger.info(f"Loading credentials from: {cred_path}")

            with open(cred_path, 'r') as f:
                creds = yaml.safe_load(f)

            mode = 'paper' if self.is_paper else 'live'
            mode_secret = creds["broker"][mode]['client_secret']
            mode_token = creds["broker"][mode]['refresh_token']

            self.client_secret = self._resolve_credential(mode_secret)
            self.refresh_token = self._resolve_credential(mode_token)

            logger.info(f"✓ Loaded credentials for {mode} mode (secret length: {len(self.client_secret)})")

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            raise

    def _resolve_credential(self, value: str) -> str:
        """Resolve credential value from environment variable"""
        if not value:
            return value

        env_pattern = r'\$\{?([A-Z_]+)\}?'
        match = re.match(env_pattern, value)

        if match:
            env_var = match.group(1)
            resolved = os.getenv(env_var)
            if not resolved:
                raise ValueError(f"Environment variable {env_var} not found")
            return resolved

        return value

    def authenticate(self) -> bool:
        """Authenticate with Tastytrade"""
        try:
            logger.info(f"Connecting to Tastytrade | {'PAPER' if self.is_paper else 'LIVE'}")

            self.session = Session(
                self.client_secret,
                self.refresh_token,
                is_test=self.is_paper
            )

            accounts = Account.get(self.session)
            self.accounts = {a.account_number: a for a in accounts}

            logger.info(f"Loaded {len(self.accounts)} account(s): {list(self.accounts.keys())}")

            if self._account_number:
                if self._account_number not in self.accounts:
                    raise ValueError(f"Account {self._account_number} not found")
                self.account = self.accounts[self._account_number]
                self.account_id = self._account_number
            else:
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
    
    async def _fetch_greeks_for_symbol(self, streamer_symbol: str) -> Optional[dm.Greeks]:
        """
        Fetch Greeks for a single option using DXLink streaming
        
        Args:
            streamer_symbol: DXLink symbol (e.g., ".QQQ260106C620")
            
        Returns:
            Greeks domain model or None
        """
        try:
            async with DXLinkStreamer(self.session) as streamer:
                await streamer.subscribe(DXGreeks, [streamer_symbol])
                
                # Get one Greeks snapshot with timeout
                try:
                    greeks_event = await asyncio.wait_for(
                        streamer.get_event(DXGreeks),
                        timeout=5.0  # 5 second timeout
                    )
                    
                    return dm.Greeks(
                        delta=Decimal(str(greeks_event.delta or 0)),
                        gamma=Decimal(str(greeks_event.gamma or 0)),
                        theta=Decimal(str(greeks_event.theta or 0)),
                        vega=Decimal(str(greeks_event.vega or 0)),
                        rho=Decimal(str(greeks_event.rho or 0)),
                        timestamp=datetime.utcnow()
                    )
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching Greeks for {streamer_symbol}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching Greeks for {streamer_symbol}: {e}")
            return None
    
    async def _fetch_greeks_batch(self, streamer_symbols: List[str]) -> Dict[str, dm.Greeks]:
        """
        Fetch Greeks for multiple options efficiently
        
        Args:
            streamer_symbols: List of DXLink symbols
            
        Returns:
            Dict mapping streamer_symbol to Greeks
        """
        greeks_map = {}
        
        if not streamer_symbols:
            return greeks_map
        
        try:
            async with DXLinkStreamer(self.session) as streamer:
                # Subscribe to all symbols at once
                await streamer.subscribe(DXGreeks, streamer_symbols)
                
                # Fetch Greeks for each symbol
                # for symbol in streamer_symbols:
                #     try:
                #         greeks_event = await asyncio.wait_for(
                #             streamer.get_event(DXGreeks),
                #             timeout=2.0
                #         )
                        
                #         greeks_map[symbol] = dm.Greeks(
                #             delta=Decimal(str(greeks_event.delta or 0)),
                #             gamma=Decimal(str(greeks_event.gamma or 0)),
                #             theta=Decimal(str(greeks_event.theta or 0)),
                #             vega=Decimal(str(greeks_event.vega or 0)),
                #             rho=Decimal(str(greeks_event.rho or 0)),
                #             timestamp=datetime.utcnow()
                #         )
            expected = set(streamer_symbols)

            while expected:
                try:
                    event = await asyncio.wait_for(
                        streamer.get_event(DXGreeks),
                        timeout=3.0
                    )

                    symbol = event.event_symbol
                    if symbol in expected:
                        greeks_map[symbol] = dm.Greeks(
                            delta=Decimal(str(event.delta or 0)),
                            gamma=Decimal(str(event.gamma or 0)),
                            theta=Decimal(str(event.theta or 0)),
                            vega=Decimal(str(event.vega or 0)),
                            rho=Decimal(str(event.rho or 0)),
                            timestamp=datetime.utcnow()
                        )
                        expected.remove(symbol)

                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for Greeks batch")
                    break
 
                   
                        
        except Exception as e:
            logger.error(f"Error in batch Greeks fetch: {e}")
        
        return greeks_map
    
    async def get_positions(self) -> List[dm.Position]:
        """
        Fetch positions with Greeks from option chain.

        This approach is more reliable than DXLink streaming:
        1. Get positions with include_marks=True
        2. Group options by underlying
        3. Fetch option chain for each underlying (has Greeks)
        4. Match positions to chain data
        """
        try:
            if not self.account:
                raise ValueError("Not authenticated")
            
            positions_data = self.account.get_positions(self.session)
            
            # First pass: collect all option streamer symbols
            option_symbols_map = {}  # streamer_symbol -> position_data
            equity_positions = []
            
            for pos_data in positions_data:
                instrument_type = pos_data.instrument_type
                
                if instrument_type == 'Equity Option':
                    # Construct streamer symbol from OCC symbol
                    # OCC: "IWM   260123P00261000" -> Streamer: ".IWM260123P261"
                    occ_symbol = pos_data.symbol
                    streamer_symbol = self._occ_to_streamer_symbol(occ_symbol)
                    if streamer_symbol:
                        option_symbols_map[streamer_symbol] = pos_data
                    else:
                        logger.warning(f"Could not convert OCC symbol: {occ_symbol}")
                else:
                    equity_positions.append(pos_data)
            
            # Fetch Greeks for all options in batch
            logger.info(f"Fetching Greeks for {len(option_symbols_map)} option positions...")
            # greeks_map = asyncio.run(self._fetch_greeks_batch(list(option_symbols_map.keys())))
            greeks_map =  await self._fetch_greeks_batch(list(option_symbols_map.keys()))

            # logger.info(f"✓ Fetched Greeks for {len(greeks_map)} options")
            
            # Second pass: create positions with Greeks
            positions = []

            for pos_data in positions_data:
                try:
                    symbol = self._parse_symbol_from_position(pos_data)

                    # Get signed quantity
                    raw_quantity = int(pos_data.quantity or 0)
                    if hasattr(pos_data, 'quantity_direction'):
                        if pos_data.quantity_direction == 'Short':
                            raw_quantity = -abs(raw_quantity)
                        else:
                            raw_quantity = abs(raw_quantity)

                    if raw_quantity == 0:
                        continue

                    # Get broker position ID
                    broker_pos_id = str(pos_data.id) if hasattr(pos_data, 'id') else None
                    if not broker_pos_id:
                        broker_pos_id = f"{self.account_id}_{symbol.ticker}"

                    # Get current price
                    current_price = Decimal('0')
                    if hasattr(pos_data, 'mark_price') and pos_data.mark_price:
                        current_price = Decimal(str(pos_data.mark_price))
                    elif hasattr(pos_data, 'close_price') and pos_data.close_price:
                        current_price = Decimal(str(pos_data.close_price))

                    # Calculate market value
                    market_value = current_price * abs(raw_quantity) * symbol.multiplier

                    # Create position
                    position = dm.Position(
                        symbol=symbol,
                        quantity=raw_quantity,
                        entry_price=Decimal(str(pos_data.average_open_price or 0)),
                        current_price=current_price,
                        market_value=market_value,
                        total_cost=Decimal(str(abs(pos_data.average_open_price or 0))) * abs(raw_quantity) * symbol.multiplier,
                        broker_position_id=broker_pos_id,
                    )

                    # Handle by asset type
                    if symbol.asset_type == dm.AssetType.EQUITY:
                        # Stock: delta = quantity
                        position.greeks = dm.Greeks(
                            delta=Decimal(str(raw_quantity)),
                            gamma=Decimal('0'),
                            theta=Decimal('0'),
                            vega=Decimal('0'),
                            rho=Decimal('0'),
                            timestamp=datetime.utcnow()
                        )
                        logger.debug(f"✓ Equity: {symbol.ticker} Δ={raw_quantity}")

                    elif symbol.asset_type == dm.AssetType.OPTION:
                        # Options: fetch from chain
                        option_positions_by_underlying[symbol.ticker].append(position)

                    positions.append(position)

                except Exception as e:
                    logger.warning(f"Skipping position due to error: {e}")
                    continue

            # Fetch option chains and populate Greeks
            if option_positions_by_underlying:
                self._populate_greeks_from_chains(option_positions_by_underlying)

            # Filter out options without Greeks
            positions = [p for p in positions if p.greeks is not None]

            logger.info(f"✓ Fetched {len(positions)} positions with Greeks")
            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            logger.exception("Full error:")
            return []
   
    def _run_async_blocking(self, coro):
        """
        Safely run async code from sync context and ALWAYS return result
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Running inside FastAPI / event loop → block safely
            return asyncio.get_event_loop().run_until_complete(coro)
        else:
            return asyncio.run(coro)


    def _occ_to_streamer_symbol(self, occ_symbol: str) -> Optional[str]:
        """
        Fetch option chains and populate Greeks for option positions.

        This is the reliable method - option chains include Greeks data.
        """
        for underlying, positions in option_positions_by_underlying.items():
            try:
                logger.info(f"Fetching option chain for {underlying}...")

                # Fetch option chain with Greeks
                chain = get_option_chain(self.session, underlying)

                if not chain:
                    logger.warning(f"No option chain data for {underlying}")
                    continue

                # Build lookup: (strike, expiration, option_type) -> greeks
                chain_lookup = {}
                for option in chain:
                    if hasattr(option, 'greeks') and option.greeks:
                        key = (
                            float(option.strike_price),
                            option.expiration_date,
                            option.option_type  # 'C' or 'P'
                        )
                        chain_lookup[key] = option.greeks

                logger.info(f"  Chain has {len(chain_lookup)} options with Greeks")

                # Match positions to chain
                for position in positions:
                    try:
                        key = (
                            float(position.symbol.strike),
                            position.symbol.expiration.date(),
                            'C' if position.symbol.option_type == dm.OptionType.CALL else 'P'
                        )

                        greeks = chain_lookup.get(key)

                        if greeks:
                            # Greeks from chain are PER CONTRACT
                            # Multiply by quantity for POSITION-LEVEL Greeks
                            position.greeks = dm.Greeks(
                                delta=Decimal(str(greeks.delta or 0)) * abs(position.quantity),
                                gamma=Decimal(str(greeks.gamma or 0)) * abs(position.quantity),
                                theta=Decimal(str(greeks.theta or 0)) * abs(position.quantity),
                                vega=Decimal(str(greeks.vega or 0)) * abs(position.quantity),
                                rho=Decimal(str(greeks.rho or 0)) * abs(position.quantity) if hasattr(greeks, 'rho') else Decimal('0'),
                                timestamp=datetime.utcnow()
                            )
                            logger.debug(f"✓ Greeks: {position.symbol.ticker} ${position.symbol.strike} Δ={position.greeks.delta:.2f}")
                        else:
                            logger.warning(f"⚠️  No Greeks in chain for {position.symbol.ticker} ${position.symbol.strike}")

                    except Exception as e:
                        logger.error(f"Error matching position to chain: {e}")
                        continue

            except Exception as e:
                logger.error(f"Failed to fetch option chain for {underlying}: {e}")
                continue

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
                logger.warning(f"Unknown instrument type: {instrument_type}")
                return dm.Symbol(
                    ticker=symbol_str,
                    asset_type=dm.AssetType.EQUITY,
                    multiplier=1
                )

        except Exception as e:
            logger.warning(f"Error parsing symbol: {e}")
            return dm.Symbol(
                ticker=pos_data.symbol,
                asset_type=dm.AssetType.EQUITY,
                multiplier=1
            )

    def _parse_occ_symbol(self, symbol_str: str) -> dm.Symbol:
        """Parse OCC format option symbol"""
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
            ticker = symbol_str[:6].strip() if len(symbol_str) >= 6 else symbol_str
            return dm.Symbol(
                ticker=ticker,
                asset_type=dm.AssetType.EQUITY,
                multiplier=1
            )
            
async def main():
    adapter = TastytradeAdapter()
    adapter.authenticate()

    positions = await adapter.get_positions()
    if positions:
        pos = positions[0]
        print(f"Position: {pos.symbol.ticker}")
        print(f"Has Greeks: {pos.greeks is not None}")
        if pos.greeks:
            print(f"Delta: {pos.greeks.delta}")

if __name__ == "__main__":
    asyncio.run(main())
