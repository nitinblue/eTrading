"""
Tastytrade Broker Adapter - DXLink Streaming for Greeks

Uses DXLinkStreamer and DXGreeks for reliable Greeks fetching.
Supports both sync and async contexts (FastAPI, standalone scripts).
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging
import yaml
from pathlib import Path
from collections import defaultdict
import asyncio
import concurrent.futures

from tastytrade import Session, Account
from tastytrade.instruments import Equity, Option
from tastytrade.streamer import DXLinkStreamer
from tastytrade.dxfeed import Greeks as DXGreeks
import os
import re

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)

# Thread pool for running async code from sync context
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class BrokerAdapter:
    """Base class for broker adapters"""

    def __init__(self, account_id: str, credentials: str):
        self.account_id = account_id
        self.credentials = credentials

    def authenticate(self) -> bool:
        raise NotImplementedError

    def get_account_balance(self) -> Dict[str, Decimal]:
        raise NotImplementedError

    async def get_positions(self) -> List[dm.Position]:
        raise NotImplementedError


class TastytradeAdapter(BrokerAdapter):
    """Tastytrade broker integration with DXLink Greeks streaming"""

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

    async def _fetch_greeks_via_dxlink(self, streamer_symbols: List[str]) -> Dict[str, dm.Greeks]:
        """
        Fetch Greeks for multiple options via DXLink streaming.

        Subscribes to all symbols and collects events until we have all
        or timeout is reached.
        """
        greeks_map = {}

        if not streamer_symbols:
            return greeks_map

        symbols_needed = set(streamer_symbols)
        timeout_seconds = 15  # Total timeout for all Greeks

        try:
            async with DXLinkStreamer(self.session) as streamer:
                # Subscribe to Greeks for all symbols
                await streamer.subscribe(DXGreeks, streamer_symbols)
                logger.info(f"Subscribed to Greeks for {len(streamer_symbols)} symbols")

                start_time = asyncio.get_event_loop().time()

                # Collect events until we have all or timeout
                while symbols_needed and (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                    try:
                        # Get next event with short timeout
                        greeks_event = await asyncio.wait_for(
                            streamer.get_event(DXGreeks),
                            timeout=2.0
                        )
                        logger.info(f"Received Greeks event: {symbols_needed}")

                        # Extract symbol from event
                        event_symbol = greeks_event.event_symbol

                        if event_symbol in symbols_needed:
                            greeks_map[event_symbol] = dm.Greeks(
                                delta=Decimal(str(greeks_event.delta or 0)),
                                gamma=Decimal(str(greeks_event.gamma or 0)),
                                theta=Decimal(str(greeks_event.theta or 0)),
                                vega=Decimal(str(greeks_event.vega or 0)),
                                rho=Decimal(str(greeks_event.rho or 0)),
                                timestamp=datetime.utcnow()
                            )
                            symbols_needed.remove(event_symbol)
                            logger.info(f"✓ Got Greeks for {event_symbol}: Δ={greeks_event.delta:.4f}")

                    except asyncio.TimeoutError:
                        # Short timeout expired, continue if we still have time
                        continue
                    except Exception as e:
                        logger.warning(f"Error getting Greeks event: {e}")
                        continue

                if symbols_needed:
                    logger.warning(f"Timeout: Missing Greeks for {len(symbols_needed)} symbols: {list(symbols_needed)[:5]}...")
                else:
                    logger.info(f"✓ Got Greeks for all {len(greeks_map)} symbols")

        except Exception as e:
            logger.error(f"DXLink streaming error: {e}")
            logger.exception("Full error:")

        return greeks_map

    def _run_async(self, coro):
        """
        Run an async coroutine from sync context.
        Handles both standalone and FastAPI (already in event loop) scenarios.
        """
        try:
            # Check if we're in an existing event loop
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an event loop (FastAPI), run in thread pool
            future = _thread_pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
        else:
            # No event loop, create one
            return asyncio.run(coro)

    def get_positions(self) -> List[dm.Position]:
        """
        Fetch positions with Greeks from DXLink streaming.

        1. Get positions from broker
        2. Convert OCC symbols to streamer symbols
        3. Fetch Greeks via DXLink streaming
        4. Attach Greeks to positions

        Works in both sync and async contexts.
        """
        try:
            if not self.account:
                raise ValueError("Not authenticated")

            # Get positions with marks
            positions_data = self.account.get_positions(
                self.session,
                include_marks=True
            )

            if not positions_data:
                logger.info("No positions found")
                return []

            logger.info(f"Fetching {len(positions_data)} positions from Tastytrade...")

            # Collect option streamer symbols and build position map
            streamer_symbols = []
            symbol_to_positions = defaultdict(list)  # streamer_symbol -> [position objects]
            positions = []

            for pos_data in positions_data:
                try:
                    symbol = self._parse_symbol_from_position(pos_data)
                    # logger.info(f"Found position Symbol: {symbol} ")

                    # Get unsigned quantity
                    raw_quantity = int(pos_data.quantity or 0)
                    if raw_quantity == 0:
                        continue

                    # Determine position direction
                    # Tastytrade API returns:
                    # - quantity_direction: 'Long' or 'Short' (enum or string)
                    # - cost_effect: 'Credit' or 'Debit' (for opening transaction)
                    #
                    # Direction logic:
                    # - Short position: negative quantity (sold to open)
                    # - Long position: positive quantity (bought to open)

                    signed_quantity = abs(raw_quantity)  # Start with positive

                    # Primary: check quantity_direction field
                    qty_dir = getattr(pos_data, 'quantity_direction', None)
                    if qty_dir is not None:
                        # Handle enum or string - check if 'Short' is anywhere in the value
                        qty_dir_str = str(qty_dir)
                        if 'Short' in qty_dir_str or 'SHORT' in qty_dir_str:
                            signed_quantity = -abs(raw_quantity)
                        logger.info(f"  {pos_data.symbol}: qty_dir={qty_dir_str} -> qty={signed_quantity}")
                    else:
                        # Fallback: use cost_effect
                        cost_effect = getattr(pos_data, 'cost_effect', None)
                        if cost_effect is not None:
                            cost_effect_str = str(cost_effect)
                            if 'Credit' in cost_effect_str or 'CREDIT' in cost_effect_str:
                                signed_quantity = -abs(raw_quantity)
                            logger.info(f"  {pos_data.symbol}: cost_effect={cost_effect_str} -> qty={signed_quantity}")
                        else:
                            logger.warning(f"  {pos_data.symbol}: no direction field, assuming long")

                    # Get broker position ID
                    broker_pos_id = str(pos_data.id) if hasattr(pos_data, 'id') else None
                    if not broker_pos_id:
                        clean_symbol = "".join(pos_data.symbol.split())
                        broker_pos_id = f"{self.account_id}_{clean_symbol}"

                    # Get current price
                    current_price = Decimal('0')
                    if hasattr(pos_data, 'mark_price') and pos_data.mark_price:
                        current_price = Decimal(str(pos_data.mark_price))
                    elif hasattr(pos_data, 'close_price') and pos_data.close_price:
                        current_price = Decimal(str(pos_data.close_price))

                    # Calculate market value
                    market_value = current_price * abs(signed_quantity) * symbol.multiplier

                    # Create position
                    position = dm.Position(
                        symbol=symbol,
                        quantity=signed_quantity,  # Signed: positive=long, negative=short
                        entry_price=Decimal(str(pos_data.average_open_price or 0)),
                        current_price=current_price,
                        market_value=market_value,
                        total_cost=Decimal(str(abs(pos_data.average_open_price or 0))) * abs(signed_quantity) * symbol.multiplier,
                        broker_position_id=broker_pos_id,
                    )

                    # Handle by asset type
                    if symbol.asset_type == dm.AssetType.EQUITY:
                        # Stock: delta = quantity (1 share = 1 delta)
                        position.greeks = dm.Greeks(
                            delta=Decimal(str(signed_quantity)),
                            gamma=Decimal('0'),
                            theta=Decimal('0'),
                            vega=Decimal('0'),
                            rho=Decimal('0'),
                            timestamp=datetime.utcnow()
                        )
                        logger.debug(f"✓ Equity: {symbol.ticker} Δ={signed_quantity}")

                    elif symbol.asset_type == dm.AssetType.OPTION:
                        # Options: need to fetch Greeks via DXLink
                        streamer_symbol = self._occ_to_streamer_symbol(pos_data.symbol)
                        if streamer_symbol:
                            streamer_symbols.append(streamer_symbol)
                            symbol_to_positions[streamer_symbol].append(position)

                    positions.append(position)

                except Exception as e:
                    logger.warning(f"Skipping position due to error: {e}")
                    continue

            # Fetch Greeks for all options via DXLink
            if streamer_symbols:
                logger.info(f"Fetching Greeks for {len(streamer_symbols)} option positions via DXLink...")
                greeks_map = self._run_async(self._fetch_greeks_via_dxlink(streamer_symbols))
                logger.info(f"✓ Fetched Greeks for {len(greeks_map)} options")
                # Attach Greeks to positions
                for streamer_symbol, greeks in greeks_map.items():
                    for position in symbol_to_positions[streamer_symbol]:
                        # Greeks are per-contract from DXLink (decimal form, e.g., 0.52)
                        # Position Greeks = per_contract * signed_qty * multiplier
                        #
                        # Examples:
                        # - Short call (qty=-1): +0.52 * -1 * 100 = -52 (negative delta)
                        # - Short put (qty=-1):  -0.33 * -1 * 100 = +33 (positive delta)
                        # - Long call (qty=1):   +0.36 * 1 * 100  = +36 (positive delta)
                        # - Long put (qty=1):    -0.22 * 1 * 100  = -22 (negative delta)

                        qty = position.quantity  # Signed quantity
                        multiplier = position.symbol.multiplier  # 100 for options

                        position.greeks = dm.Greeks(
                            delta=greeks.delta * qty * multiplier,
                            gamma=greeks.gamma * abs(qty) * multiplier,
                            theta=greeks.theta * qty * multiplier,
                            vega=greeks.vega * qty * multiplier,
                            rho=greeks.rho * qty * multiplier,
                            timestamp=greeks.timestamp
                        )
                        direction = "SHORT" if qty < 0 else "LONG"
                        logger.info(f"  {direction} {streamer_symbol}: qty={qty}, Δ={position.greeks.delta:.2f}, Θ={position.greeks.theta:.2f}")

            # Filter out options without Greeks
            positions_with_greeks = [p for p in positions if p.greeks is not None]
            missing_count = len(positions) - len(positions_with_greeks)
            if missing_count > 0:
                logger.warning(f"⚠️ {missing_count} positions missing Greeks")

            logger.info(f"✓ Fetched {len(positions_with_greeks)} positions with Greeks")
            return positions_with_greeks

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            logger.exception("Full error:")
            return []

    def _occ_to_streamer_symbol(self, occ_symbol: str) -> Optional[str]:
        """
        Convert OCC symbol to DXLink streamer symbol.

        OCC:      "IWM   260213P00263000"
        Streamer: ".IWM260213P263"

        Format: .{TICKER}{YYMMDD}{C/P}{STRIKE}
        """
        try:
            # Clean up ticker (remove spaces)
            ticker = occ_symbol[:6].strip()
            exp_date = occ_symbol[6:12]  # YYMMDD
            option_type = occ_symbol[12]  # C or P
            strike_str = occ_symbol[13:21]  # 00263000

            # Convert strike: 00263000 -> 263
            strike_int = int(strike_str) // 1000

            # Build streamer symbol
            streamer_symbol = f".{ticker}{exp_date}{option_type}{strike_int}"

            return streamer_symbol

        except Exception as e:
            logger.error(f"Error converting OCC to streamer symbol: {occ_symbol} - {e}")
            return None

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


if __name__ == "__main__":
    adapter = TastytradeAdapter()
    adapter.authenticate()

    positions = adapter.get_positions()
    if positions:
        print(f"\nFetched {len(positions)} positions:")
        for pos in positions:
            if pos.greeks:
                print(f"  {pos.symbol.ticker}: qty={pos.quantity}, Δ={pos.greeks.delta:.2f}, Θ={pos.greeks.theta:.2f}")
            else:
                print(f"  {pos.symbol.ticker}: qty={pos.quantity}, NO GREEKS")
