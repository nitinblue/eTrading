"""
Portfolio Analysis Runner - Main Entry Point (ASYNC Version)

Flow: Tastytrade API → Database → Display
1. Fetch fresh data from broker (async)
2. Update database
3. Query database for display

Using async/await for better performance with I/O operations
"""

import logging
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from collections import defaultdict
from tabulate import tabulate
import sys

# Import your modules
import data_model as dm
from broker_adapters import TastytradeAdapter
from data_access import (
    PortfolioRepository, TradeRepository, PositionRepository, 
    OrderRepository
)

from data_model import (
    get_session, init_database
)

from service_layer import PortfolioService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PortfolioAnalyzer:
    """Main class to analyze and display portfolio data"""
    
    def __init__(self, db_url: str = "sqlite:///portfolio.db"):
        """
        Initialize analyzer
        
        Args:
            db_url: Database connection string
        """
        # Initialize database
        logger.info(f"Initializing database: {db_url}")
        self.engine = init_database(db_url)
        self.session = get_session(self.engine)
        
        # Broker and service will be initialized in async_init
        self.broker = None
        self.service = None
        
        # Repositories (synchronous database access)
        self.portfolio_repo = PortfolioRepository(self.session)
        self.position_repo = PositionRepository(self.session)
        self.trade_repo = TradeRepository(self.session)
        
        self.portfolio = None
    
    async def async_init(self):
        """Async initialization for broker connection"""
        logger.info("Creating Tastytrade adapter...")
        self.broker = TastytradeAdapter()
        
        # Authenticate (potentially async in future)
        if not self.broker.authenticate():
            raise RuntimeError("Failed to authenticate with Tastytrade")
        
        # Create service
        self.service = PortfolioService(self.session, self.broker)
        
        logger.info(f"✓ Connected to Tastytrade account: {self.broker.account_id}")
    
    async def sync_portfolio(self, portfolio_name: str = "Main Portfolio") -> dm.Portfolio:
        """
        Step 1: Sync from broker to database (ASYNC)
        
        Flow: Tastytrade API → Service Layer → Database
        
        This is async because it makes multiple API calls that can be parallelized
        """
        logger.info("=" * 80)
        logger.info("SYNCING FROM TASTYTRADE")
        logger.info("=" * 80)
        
        # Create or get portfolio
        existing = self.portfolio_repo.get_by_account(
            broker="tastytrade",
            account_id=self.broker.account_id
        )
        
        if existing:
            logger.info(f"Found existing portfolio: {existing.name}")
            # Use await for async service method
            self.portfolio = await self.service.sync_from_broker(existing.id)
        else:
            logger.info(f"Creating new portfolio: {portfolio_name}")
            # Use await for async service method
            self.portfolio = await self.service.create_portfolio_from_broker(
                broker_name="tastytrade",
                account_id=self.broker.account_id,
                name=portfolio_name
            )
        
        logger.info(f"✓ Sync complete - Portfolio ID: {self.portfolio.id}")
        logger.info("")
        return self.portfolio
    
    def display_portfolio_summary(self):
        """
        Step 2: Display portfolio summary from database
        
        Flow: Database → Display (synchronous - just reading from DB)
        """
        if not self.portfolio:
            logger.error("No portfolio loaded. Run sync_portfolio() first.")
            return
        
        print("\n" + "=" * 80)
        print("PORTFOLIO SUMMARY")
        print("=" * 80)
        
        summary_data = [
            ["Portfolio Name", self.portfolio.name],
            ["Broker", self.portfolio.broker],
            ["Account", self.portfolio.account_id],
            ["Last Updated", self.portfolio.last_updated.strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""],
            ["Cash Balance", f"${self.portfolio.cash_balance:,.2f}"],
            ["Buying Power", f"${self.portfolio.buying_power:,.2f}"],
            ["Total Equity", f"${self.portfolio.total_equity:,.2f}"],
            ["Total P&L", f"${self.portfolio.total_pnl:,.2f}"],
            ["", ""],
            ["Portfolio Delta", f"{self.portfolio.portfolio_delta:.2f}"],
            ["Portfolio Gamma", f"{self.portfolio.portfolio_gamma:.4f}"],
            ["Portfolio Theta", f"{self.portfolio.portfolio_theta:.2f}"],
            ["Portfolio Vega", f"{self.portfolio.portfolio_vega:.2f}"],
        ]
        
        print(tabulate(summary_data, tablefmt="grid"))
        print("")
    
    def display_positions_by_underlying(self):
        """
        Step 3: Display positions grouped by underlying
        
        Flow: Database → Group by underlying → Display with trade details
        """
        if not self.portfolio:
            logger.error("No portfolio loaded. Run sync_portfolio() first.")
            return
        
        # Get all positions from database
        positions = self.position_repo.get_by_portfolio(self.portfolio.id)
        
        if not positions:
            print("\n📭 No positions found.\n")
            return
        
        # Group positions by underlying symbol
        by_underlying = defaultdict(list)
        for pos in positions:
            underlying = self._get_underlying(pos.symbol)
            by_underlying[underlying].append(pos)
        
        print("\n" + "=" * 120)
        print(f"POSITIONS BY UNDERLYING ({len(by_underlying)} underlyings, {len(positions)} total positions)")
        print("=" * 120)
        
        for underlying, positions_list in sorted(by_underlying.items()):
            self._display_underlying_positions(underlying, positions_list)
    
    def _display_underlying_positions(self, underlying: str, positions: List[dm.Position]):
        """Display all positions for a single underlying"""
    
        print(f"\n{'─' * 120}")
        print(f"🎯 {underlying}")
        print(f"{'─' * 120}")
        
        # Calculate totals
        total_delta = sum(p.delta for p in positions)
        total_gamma = sum(p.gamma for p in positions)
        total_theta = sum(p.theta for p in positions)
        total_vega = sum(p.vega for p in positions)
        total_pnl = sum(p.unrealized_pnl() for p in positions)
        total_value = sum(p.market_value for p in positions)
        
        # Header with summary
        print(f"Positions: {len(positions)} | "
            f"Market Value: ${total_value:,.2f} | "
            f"P&L: ${total_pnl:,.2f} | "
            f"Δ={total_delta:.2f} Γ={total_gamma:.4f} Θ={total_theta:.2f} V={total_vega:.2f}")
        print("")
        
        # Build position table
        headers = [
            "Symbol", "Type", "Exp", "Strike", "Side",
            "Qty", "Entry $", "Current $", "Market Value",
            "Delta", "Gamma", "Theta", "Vega",
            "P&L", "P&L %"
        ]
        
        rows = []
        for pos in sorted(positions, key=lambda p: self._position_sort_key(p)):
            symbol = pos.symbol
            
            # Determine Long/Short based on quantity sign
            is_long = pos.quantity > 0
            
            # Format symbol details
            if symbol.asset_type == dm.AssetType.OPTION:
                sym_display = symbol.ticker
                opt_type = "CALL" if symbol.option_type == dm.OptionType.CALL else "PUT"
                exp_display = symbol.expiration.strftime("%m/%d/%y") if symbol.expiration else "-"
                strike_display = f"${symbol.strike:.0f}"
                side = "LONG" if is_long else "SHORT"
            else:
                sym_display = symbol.ticker
                opt_type = "STOCK"
                exp_display = "-"
                strike_display = "-"
                side = "LONG" if is_long else "SHORT"
            
            # Calculate P&L
            unrealized_pnl = pos.unrealized_pnl()
            pnl_percent = (unrealized_pnl / pos.total_cost * 100) if pos.total_cost else 0
            
            # Format row
            row = [
                sym_display,
                opt_type,
                exp_display,
                strike_display,
                side,
                abs(pos.quantity),  # Show absolute quantity
                f"${pos.average_price:.2f}",
                f"${pos.current_price:.2f}" if pos.current_price else "-",
                f"${pos.market_value:,.2f}",
                f"{pos.delta:.2f}",
                f"{pos.gamma:.4f}",
                f"{pos.theta:.2f}",
                f"{pos.vega:.2f}",
                f"${unrealized_pnl:,.2f}",
                f"{pnl_percent:.1f}%"
            ]
            rows.append(row)
        
        # Add total row
        rows.append([
            "─" * 10, "─" * 6, "─" * 8, "─" * 8, "─" * 5,
            "─" * 5, "─" * 10, "─" * 10, "─" * 12,
            "─" * 8, "─" * 8, "─" * 8, "─" * 8,
            "─" * 12, "─" * 8
        ])
        rows.append([
            "TOTAL", "", "", "", "",
            "", "", "", f"${total_value:,.2f}",
            f"{total_delta:.2f}",
            f"{total_gamma:.4f}",
            f"{total_theta:.2f}",
            f"{total_vega:.2f}",
            f"${total_pnl:,.2f}",
            ""
        ])
        
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    
    def display_trades_with_legs(self):
        """
        Step 4: Display trades with their legs
        
        Flow: Database → Group legs by trade → Display hierarchically
        """
        if not self.portfolio:
            logger.error("No portfolio loaded. Run sync_portfolio() first.")
            return
        
        # Get open trades from database
        open_trades = self.trade_repo.get_by_portfolio(self.portfolio.id, open_only=True)
        
        if not open_trades:
            print("\n📭 No open trades found.\n")
            return
        
        print("\n" + "=" * 140)
        print(f"OPEN TRADES ({len(open_trades)} trades)")
        print("=" * 140)
        
        for trade in sorted(open_trades, key=lambda t: t.underlying_symbol):
            self._display_trade_with_legs(trade)
    
    def _display_trade_with_legs(self, trade: dm.Trade):
        """Display a single trade with all its legs"""
        
        print(f"\n{'═' * 140}")
        
        # Trade header
        strategy_name = trade.strategy.name if trade.strategy else "Single Position"
        strategy_type = trade.strategy.strategy_type.value if trade.strategy else "single"
        
        trade_pnl = trade.total_pnl()
        net_cost = trade.net_cost()
        pnl_percent = (trade_pnl / abs(net_cost) * 100) if net_cost != 0 else 0
        
        # Calculate trade-level Greeks (sum from legs)
        trade_delta = sum(leg.symbol.multiplier * leg.quantity * 
                         self._estimate_delta(leg) for leg in trade.legs)
        trade_theta = sum(leg.symbol.multiplier * leg.quantity * 
                         self._estimate_theta(leg) for leg in trade.legs)
        
        print(f"🎲 TRADE: {trade.underlying_symbol} - {strategy_name} ({strategy_type})")
        print(f"   Opened: {trade.opened_at.strftime('%Y-%m-%d %H:%M')} | "
              f"Legs: {len(trade.legs)} | "
              f"Net Cost: ${net_cost:,.2f} | "
              f"P&L: ${trade_pnl:,.2f} ({pnl_percent:+.1f}%) | "
              f"Δ={trade_delta:.2f} Θ={trade_theta:.2f}")
        
        if trade.notes:
            print(f"   Notes: {trade.notes}")
        
        print(f"{'─' * 140}")
        
        # Legs table
        headers = [
            "Leg", "Symbol", "Type", "Exp", "Strike", "Side", 
            "Qty", "Entry $", "Current $", "Entry Time",
            "Delta", "Gamma", "Theta", "Vega",
            "Leg P&L", "Fees"
        ]
        
        rows = []
        for i, leg in enumerate(trade.legs, 1):
            symbol = leg.symbol
            
            # Format symbol details
            if symbol.asset_type == dm.AssetType.OPTION:
                sym_display = f"{symbol.ticker}"
                opt_type = "C" if symbol.option_type == dm.OptionType.CALL else "P"
                exp_display = symbol.expiration.strftime("%m/%d") if symbol.expiration else "-"
                strike_display = f"${symbol.strike:.0f}"
            else:
                sym_display = symbol.ticker
                opt_type = "STK"
                exp_display = "-"
                strike_display = "-"
            
            # Side
            side_map = {
                dm.OrderSide.BUY_TO_OPEN: "BTO",
                dm.OrderSide.SELL_TO_OPEN: "STO",
                dm.OrderSide.BUY_TO_CLOSE: "BTC",
                dm.OrderSide.SELL_TO_CLOSE: "STC",
                dm.OrderSide.BUY: "BUY",
                dm.OrderSide.SELL: "SELL"
            }
            side_display = side_map.get(leg.side, str(leg.side))
            
            # Calculate leg P&L
            if trade.is_open:
                leg_pnl = leg.unrealized_pnl()
            else:
                leg_pnl = leg.realized_pnl()
            
            # Estimate Greeks for leg
            leg_delta = self._estimate_delta(leg)
            leg_gamma = 0.0
            leg_theta = self._estimate_theta(leg)
            leg_vega = 0.0
            
            row = [
                f"#{i}",
                sym_display,
                opt_type,
                exp_display,
                strike_display,
                side_display,
                abs(leg.quantity),
                f"${leg.entry_price:.2f}" if leg.entry_price else "-",
                f"${leg.current_price:.2f}" if leg.current_price else "-",
                leg.entry_time.strftime("%m/%d %H:%M") if leg.entry_time else "-",
                f"{leg_delta:.2f}",
                f"{leg_gamma:.4f}",
                f"{leg_theta:.2f}",
                f"{leg_vega:.2f}",
                f"${leg_pnl:,.2f}",
                f"${leg.fees:.2f}"
            ]
            rows.append(row)
        
        # Add total row for legs
        total_leg_pnl = sum(leg.unrealized_pnl() if trade.is_open else leg.realized_pnl() 
                           for leg in trade.legs)
        total_fees = sum(leg.fees for leg in trade.legs)
        
        rows.append([
            "─" * 4, "─" * 8, "─" * 4, "─" * 8, "─" * 8, "─" * 4,
            "─" * 5, "─" * 10, "─" * 10, "─" * 12,
            "─" * 8, "─" * 8, "─" * 8, "─" * 8,
            "─" * 12, "─" * 8
        ])
        rows.append([
            "TOTAL", "", "", "", "", "",
            "", "", "", "",
            f"{trade_delta:.2f}",
            "",
            f"{trade_theta:.2f}",
            "",
            f"${total_leg_pnl:,.2f}",
            f"${total_fees:.2f}"
        ])
        
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    
    async def display_option_chains(self, underlyings: Optional[List[str]] = None):
        """
        Step 5: Display option chains for analysis (ASYNC)
        
        Flow: Tastytrade API → Display (not stored in DB for now)
        
        This is async because we may fetch multiple chains concurrently
        """
        if not underlyings:
            # Get unique underlyings from positions
            positions = self.position_repo.get_by_portfolio(self.portfolio.id)
            underlyings = list(set(self._get_underlying(p.symbol) for p in positions))
        
        if not underlyings:
            print("\n📭 No underlyings to fetch option chains for.\n")
            return
        
        print("\n" + "=" * 100)
        print(f"OPTION CHAINS")
        print("=" * 100)
        
        # Fetch all chains concurrently
        tasks = [self._fetch_and_display_chain(underlying) for underlying in sorted(underlyings)]
        await asyncio.gather(*tasks)
    
    async def _fetch_and_display_chain(self, underlying: str):
        """Fetch and display option chain for a single underlying (async)"""
        
        print(f"\n{'─' * 100}")
        print(f"📊 {underlying} Option Chain")
        print(f"{'─' * 100}")
        
        try:
            # Fetch from broker (potentially async in future)
            # For now, run in executor to not block
            chain = await asyncio.to_thread(self.broker.get_option_chain, underlying)
            
            if not chain:
                print(f"   No options available for {underlying}")
                return
            
            # Group by expiration
            by_expiration = defaultdict(list)
            for option in chain:
                exp_date = option.expiration.strftime("%Y-%m-%d") if option.expiration else "Unknown"
                by_expiration[exp_date].append(option)
            
            # Display first 3 expirations
            for exp_date in sorted(by_expiration.keys())[:3]:
                options = by_expiration[exp_date]
                
                print(f"\n   Expiration: {exp_date} ({len(options)} contracts)")
                
                # Group by strike
                by_strike = defaultdict(lambda: {"call": None, "put": None})
                for opt in options:
                    strike = float(opt.strike)
                    if opt.option_type == dm.OptionType.CALL:
                        by_strike[strike]["call"] = opt
                    else:
                        by_strike[strike]["put"] = opt
                
                # Display table (showing first 10 strikes)
                headers = ["Strike", "Call Symbol", "Put Symbol"]
                rows = []
                
                for strike in sorted(by_strike.keys())[:10]:
                    call_opt = by_strike[strike]["call"]
                    put_opt = by_strike[strike]["put"]
                    
                    call_symbol = call_opt.get_option_symbol() if call_opt else "-"
                    put_symbol = put_opt.get_option_symbol() if put_opt else "-"
                    
                    rows.append([
                        f"${strike:.2f}",
                        call_symbol,
                        put_symbol
                    ])
                
                print(tabulate(rows, headers=headers, tablefmt="simple", maxcolwidths=[None, 40, 40]))
                
        except Exception as e:
            logger.error(f"Failed to fetch option chain for {underlying}: {e}")
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _get_underlying(self, symbol: dm.Symbol) -> str:
        """Get underlying symbol (ticker for stocks, underlying for options)"""
        return symbol.ticker
    
    def _position_sort_key(self, position: dm.Position):
        """Sort key for positions: stock first, then by expiration, then strike"""
        symbol = position.symbol
        
        if symbol.asset_type == dm.AssetType.EQUITY:
            return (0, "", 0, 0)  # Stocks first
        elif symbol.asset_type == dm.AssetType.OPTION:
            exp_sort = symbol.expiration.strftime("%Y%m%d") if symbol.expiration else "99999999"
            opt_type_sort = 0 if symbol.option_type == dm.OptionType.PUT else 1
            strike_sort = float(symbol.strike) if symbol.strike else 0
            return (1, exp_sort, opt_type_sort, strike_sort)
        else:
            return (2, "", 0, 0)
    
    def _estimate_delta(self, leg: dm.Leg) -> float:
        """
        Estimate delta for a leg
        In production, get from position or calculate properly
        """
        if leg.symbol.asset_type == dm.AssetType.EQUITY:
            return 1.0 * (1 if leg.quantity > 0 else -1)
        # For options, would need proper calculation or fetch from position
        return 0.0
    
    def _estimate_theta(self, leg: dm.Leg) -> float:
        """
        Estimate theta for a leg
        In production, get from position or calculate properly
        """
        # Simplified - would need proper calculation
        return 0.0

async def display_option_chains_with_greeks(self, underlyings: Optional[List[str]] = None, max_expirations: int = 2):
    """
    Display option chains with Greeks for strategy building
    
    Shows separate tables:
    1. Chain overview (strikes, symbols)
    2. Greeks table (for risk analysis)
    3. Pricing table (bid/ask/IV)
    """
    if not underlyings:
        # Get unique underlyings from positions
        positions = self.position_repo.get_by_portfolio(self.portfolio.id)
        underlyings = list(set(self._get_underlying(p.symbol) for p in positions))
    
    if not underlyings:
        print("\n📭 No underlyings to fetch option chains for.\n")
        return
    
    print("\n" + "=" * 140)
    print(f"OPTION CHAINS WITH GREEKS")
    print("=" * 140)
    
    # Fetch all chains concurrently
    for underlying in sorted(underlyings):
        await self._display_chain_with_greeks(underlying, max_expirations)

async def _display_chain_with_greeks(self, underlying: str, max_expirations: int = 2):
    """Display option chain with separate tables for chain, Greeks, and pricing"""
    
    print(f"\n{'═' * 140}")
    print(f"📊 {underlying} Option Chain with Greeks")
    print(f"{'═' * 140}")
    
    try:
        # Fetch chain from broker
        chain = await asyncio.to_thread(self.broker.get_option_chain, underlying)
        
        if not chain:
            print(f"   No options available for {underlying}")
            return
        
        # Get current underlying price (would need to fetch from broker)
        # For now, use a placeholder
        underlying_price = await self._get_underlying_price(underlying)
        print(f"Underlying Price: ${underlying_price:.2f}")
        print("")
        
        # Group by expiration
        by_expiration = defaultdict(list)
        for option in chain:
            exp_date = option.expiration.strftime("%Y-%m-%d") if option.expiration else "Unknown"
            by_expiration[exp_date].append(option)
        
        # Display first N expirations
        for exp_date in sorted(by_expiration.keys())[:max_expirations]:
            options = by_expiration[exp_date]
            
            # Calculate DTE (days to expiration)
            exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
            dte = (exp_dt - datetime.now()).days
            
            print(f"\n{'─' * 140}")
            print(f"Expiration: {exp_date} ({dte} DTE) - {len(options)} contracts")
            print(f"{'─' * 140}")
            
            # Group by strike
            by_strike = defaultdict(lambda: {"call": None, "put": None})
            for opt in options:
                strike = float(opt.strike)
                if opt.option_type == dm.OptionType.CALL:
                    by_strike[strike]["call"] = opt
                else:
                    by_strike[strike]["put"] = opt
            
            # TABLE 1: Strike Overview
            print("\n1️⃣  STRIKE OVERVIEW")
            self._display_strike_table(by_strike, underlying_price)
            
            # TABLE 2: Greeks Analysis
            print("\n2️⃣  GREEKS ANALYSIS")
            await self._display_greeks_table(by_strike, underlying)
            
            # TABLE 3: Pricing & Volatility
            print("\n3️⃣  PRICING & VOLATILITY")
            await self._display_pricing_table(by_strike, underlying)
            
    except Exception as e:
        logger.error(f"Failed to fetch option chain for {underlying}: {e}")
        logger.exception("Full error:")

def _display_strike_table(self, by_strike: Dict, underlying_price: float):
    """Display basic strike information"""
    
    headers = ["Strike", "Call Symbol", "Put Symbol", "ATM"]
    rows = []
    
    # Find ATM strike
    strikes = sorted(by_strike.keys())
    atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
    
    for strike in strikes[:15]:  # Show 15 strikes
        call_opt = by_strike[strike]["call"]
        put_opt = by_strike[strike]["put"]
        
        call_symbol = call_opt.get_option_symbol()[:25] if call_opt else "-"
        put_symbol = put_opt.get_option_symbol()[:25] if put_opt else "-"
        
        # Mark ATM strike
        atm_marker = "🎯 ATM" if abs(strike - atm_strike) < 0.01 else ""
        
        rows.append([
            f"${strike:.2f}",
            call_symbol,
            put_symbol,
            atm_marker
        ])
    
    print(tabulate(rows, headers=headers, tablefmt="simple"))

async def _display_greeks_table(self, by_strike: Dict, underlying: str):
    """Display Greeks for each strike"""
    
    headers = [
        "Strike", 
        "Call Δ", "Call Γ", "Call Θ", "Call V",
        "Put Δ", "Put Γ", "Put Θ", "Put V"
    ]
    rows = []
    
    for strike in sorted(by_strike.keys())[:15]:
        call_opt = by_strike[strike]["call"]
        put_opt = by_strike[strike]["put"]
        
        # Fetch Greeks from Tastytrade (if available)
        # For now, use placeholder values - you'd fetch real Greeks
        call_greeks = await self._get_option_greeks(call_opt) if call_opt else {}
        put_greeks = await self._get_option_greeks(put_opt) if put_opt else {}
        
        row = [
            f"${strike:.2f}",
            f"{call_greeks.get('delta', 0):.3f}",
            f"{call_greeks.get('gamma', 0):.4f}",
            f"{call_greeks.get('theta', 0):.2f}",
            f"{call_greeks.get('vega', 0):.2f}",
            f"{put_greeks.get('delta', 0):.3f}",
            f"{put_greeks.get('gamma', 0):.4f}",
            f"{put_greeks.get('theta', 0):.2f}",
            f"{put_greeks.get('vega', 0):.2f}",
        ]
        rows.append(row)
    
    print(tabulate(rows, headers=headers, tablefmt="simple"))

async def _display_pricing_table(self, by_strike: Dict, underlying: str):
    """Display bid/ask/mid/IV/volume for each strike"""
    
    headers = [
        "Strike",
        "Call Bid", "Call Ask", "Call Mid", "Call IV", "Call Vol",
        "Put Bid", "Put Ask", "Put Mid", "Put IV", "Put Vol"
    ]
    rows = []
    
    for strike in sorted(by_strike.keys())[:15]:
        call_opt = by_strike[strike]["call"]
        put_opt = by_strike[strike]["put"]
        
        # Fetch market data
        call_quote = await self._get_option_quote(call_opt) if call_opt else {}
        put_quote = await self._get_option_quote(put_opt) if put_opt else {}
        
        row = [
            f"${strike:.2f}",
            f"${call_quote.get('bid', 0):.2f}",
            f"${call_quote.get('ask', 0):.2f}",
            f"${call_quote.get('mid', 0):.2f}",
            f"{call_quote.get('iv', 0):.1f}%",
            f"{call_quote.get('volume', 0):,}",
            f"${put_quote.get('bid', 0):.2f}",
            f"${put_quote.get('ask', 0):.2f}",
            f"${put_quote.get('mid', 0):.2f}",
            f"{put_quote.get('iv', 0):.1f}%",
            f"{put_quote.get('volume', 0):,}",
        ]
        rows.append(row)
    
    print(tabulate(rows, headers=headers, tablefmt="simple"))

async def _get_underlying_price(self, symbol: str) -> float:
    """Get current price of underlying"""
    try:
        quote = await asyncio.to_thread(self.broker.get_quote, symbol)
        return float(quote.get('last', 0))
    except:
        return 0.0

async def _get_option_greeks(self, option: dm.Symbol) -> Dict:
    """Fetch Greeks for an option (placeholder - implement with real data)"""
    # You would fetch from Tastytrade here
    # For now, return placeholder
    return {
        'delta': 0.5,
        'gamma': 0.01,
        'theta': -0.05,
        'vega': 0.15
    }

async def _get_option_quote(self, option: dm.Symbol) -> Dict:
    """Fetch quote for an option"""
    try:
        symbol_str = option.get_option_symbol()
        quote = await asyncio.to_thread(self.broker.get_quote, symbol_str)
        
        bid = float(quote.get('bid', 0))
        ask = float(quote.get('ask', 0))
        mid = (bid + ask) / 2 if bid and ask else 0
        
        return {
            'bid': bid,
            'ask': ask,
            'mid': mid,
            'last': float(quote.get('last', 0)),
            'iv': float(quote.get('iv', 0)) * 100,  # Convert to percentage
            'volume': int(quote.get('volume', 0)),
            'open_interest': int(quote.get('open_interest', 0))
        }
    except:
        return {'bid': 0, 'ask': 0, 'mid': 0, 'iv': 0, 'volume': 0}
    
async def display_option_chains_with_greeks(self, underlyings: Optional[List[str]] = None, max_expirations: int = 2):
    """
    Display option chains with Greeks for strategy building
    
    Shows separate tables:
    1. Chain overview (strikes, symbols)
    2. Greeks table (for risk analysis)
    3. Pricing table (bid/ask/IV)
    """
    if not underlyings:
        # Get unique underlyings from positions
        positions = self.position_repo.get_by_portfolio(self.portfolio.id)
        underlyings = list(set(self._get_underlying(p.symbol) for p in positions))
    
    if not underlyings:
        print("\n📭 No underlyings to fetch option chains for.\n")
        return
    
    print("\n" + "=" * 140)
    print(f"OPTION CHAINS WITH GREEKS")
    print("=" * 140)
    
    # Fetch all chains concurrently
    for underlying in sorted(underlyings):
        await self._display_chain_with_greeks(underlying, max_expirations)

async def _display_chain_with_greeks(self, underlying: str, max_expirations: int = 2):
    """Display option chain with separate tables for chain, Greeks, and pricing"""
    
    print(f"\n{'═' * 140}")
    print(f"📊 {underlying} Option Chain with Greeks")
    print(f"{'═' * 140}")
    
    try:
        # Fetch chain from broker
        chain = await asyncio.to_thread(self.broker.get_option_chain, underlying)
        
        if not chain:
            print(f"   No options available for {underlying}")
            return
        
        # Get current underlying price (would need to fetch from broker)
        # For now, use a placeholder
        underlying_price = await self._get_underlying_price(underlying)
        print(f"Underlying Price: ${underlying_price:.2f}")
        print("")
        
        # Group by expiration
        by_expiration = defaultdict(list)
        for option in chain:
            exp_date = option.expiration.strftime("%Y-%m-%d") if option.expiration else "Unknown"
            by_expiration[exp_date].append(option)
        
        # Display first N expirations
        for exp_date in sorted(by_expiration.keys())[:max_expirations]:
            options = by_expiration[exp_date]
            
            # Calculate DTE (days to expiration)
            exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
            dte = (exp_dt - datetime.now()).days
            
            print(f"\n{'─' * 140}")
            print(f"Expiration: {exp_date} ({dte} DTE) - {len(options)} contracts")
            print(f"{'─' * 140}")
            
            # Group by strike
            by_strike = defaultdict(lambda: {"call": None, "put": None})
            for opt in options:
                strike = float(opt.strike)
                if opt.option_type == dm.OptionType.CALL:
                    by_strike[strike]["call"] = opt
                else:
                    by_strike[strike]["put"] = opt
            
            # TABLE 1: Strike Overview
            print("\n1️⃣  STRIKE OVERVIEW")
            self._display_strike_table(by_strike, underlying_price)
            
            # TABLE 2: Greeks Analysis
            print("\n2️⃣  GREEKS ANALYSIS")
            await self._display_greeks_table(by_strike, underlying)
            
            # TABLE 3: Pricing & Volatility
            print("\n3️⃣  PRICING & VOLATILITY")
            await self._display_pricing_table(by_strike, underlying)
            
    except Exception as e:
        logger.error(f"Failed to fetch option chain for {underlying}: {e}")
        logger.exception("Full error:")

def _display_strike_table(self, by_strike: Dict, underlying_price: float):
    """Display basic strike information"""
    
    headers = ["Strike", "Call Symbol", "Put Symbol", "ATM"]
    rows = []
    
    # Find ATM strike
    strikes = sorted(by_strike.keys())
    atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
    
    for strike in strikes[:15]:  # Show 15 strikes
        call_opt = by_strike[strike]["call"]
        put_opt = by_strike[strike]["put"]
        
        call_symbol = call_opt.get_option_symbol()[:25] if call_opt else "-"
        put_symbol = put_opt.get_option_symbol()[:25] if put_opt else "-"
        
        # Mark ATM strike
        atm_marker = "🎯 ATM" if abs(strike - atm_strike) < 0.01 else ""
        
        rows.append([
            f"${strike:.2f}",
            call_symbol,
            put_symbol,
            atm_marker
        ])
    
    print(tabulate(rows, headers=headers, tablefmt="simple"))

async def _display_greeks_table(self, by_strike: Dict, underlying: str):
    """Display Greeks for each strike"""
    
    headers = [
        "Strike", 
        "Call Δ", "Call Γ", "Call Θ", "Call V",
        "Put Δ", "Put Γ", "Put Θ", "Put V"
    ]
    rows = []
    
    for strike in sorted(by_strike.keys())[:15]:
        call_opt = by_strike[strike]["call"]
        put_opt = by_strike[strike]["put"]
        
        # Fetch Greeks from Tastytrade (if available)
        # For now, use placeholder values - you'd fetch real Greeks
        call_greeks = await self._get_option_greeks(call_opt) if call_opt else {}
        put_greeks = await self._get_option_greeks(put_opt) if put_opt else {}
        
        row = [
            f"${strike:.2f}",
            f"{call_greeks.get('delta', 0):.3f}",
            f"{call_greeks.get('gamma', 0):.4f}",
            f"{call_greeks.get('theta', 0):.2f}",
            f"{call_greeks.get('vega', 0):.2f}",
            f"{put_greeks.get('delta', 0):.3f}",
            f"{put_greeks.get('gamma', 0):.4f}",
            f"{put_greeks.get('theta', 0):.2f}",
            f"{put_greeks.get('vega', 0):.2f}",
        ]
        rows.append(row)
    
    print(tabulate(rows, headers=headers, tablefmt="simple"))

async def _display_pricing_table(self, by_strike: Dict, underlying: str):
    """Display bid/ask/mid/IV/volume for each strike"""
    
    headers = [
        "Strike",
        "Call Bid", "Call Ask", "Call Mid", "Call IV", "Call Vol",
        "Put Bid", "Put Ask", "Put Mid", "Put IV", "Put Vol"
    ]
    rows = []
    
    for strike in sorted(by_strike.keys())[:15]:
        call_opt = by_strike[strike]["call"]
        put_opt = by_strike[strike]["put"]
        
        # Fetch market data
        call_quote = await self._get_option_quote(call_opt) if call_opt else {}
        put_quote = await self._get_option_quote(put_opt) if put_opt else {}
        
        row = [
            f"${strike:.2f}",
            f"${call_quote.get('bid', 0):.2f}",
            f"${call_quote.get('ask', 0):.2f}",
            f"${call_quote.get('mid', 0):.2f}",
            f"{call_quote.get('iv', 0):.1f}%",
            f"{call_quote.get('volume', 0):,}",
            f"${put_quote.get('bid', 0):.2f}",
            f"${put_quote.get('ask', 0):.2f}",
            f"${put_quote.get('mid', 0):.2f}",
            f"{put_quote.get('iv', 0):.1f}%",
            f"{put_quote.get('volume', 0):,}",
        ]
        rows.append(row)
    
    print(tabulate(rows, headers=headers, tablefmt="simple"))

async def _get_underlying_price(self, symbol: str) -> float:
    """Get current price of underlying"""
    try:
        quote = await asyncio.to_thread(self.broker.get_quote, symbol)
        return float(quote.get('last', 0))
    except:
        return 0.0

async def _get_option_greeks(self, option: dm.Symbol) -> Dict:
    """Fetch Greeks for an option (placeholder - implement with real data)"""
    # You would fetch from Tastytrade here
    # For now, return placeholder
    return {
        'delta': 0.5,
        'gamma': 0.01,
        'theta': -0.05,
        'vega': 0.15
    }

async def _get_option_quote(self, option: dm.Symbol) -> Dict:
    """Fetch quote for an option"""
    try:
        symbol_str = option.get_option_symbol()
        quote = await asyncio.to_thread(self.broker.get_quote, symbol_str)
        
        bid = float(quote.get('bid', 0))
        ask = float(quote.get('ask', 0))
        mid = (bid + ask) / 2 if bid and ask else 0
        
        return {
            'bid': bid,
            'ask': ask,
            'mid': mid,
            'last': float(quote.get('last', 0)),
            'iv': float(quote.get('iv', 0)) * 100,  # Convert to percentage
            'volume': int(quote.get('volume', 0)),
            'open_interest': int(quote.get('open_interest', 0))
        }
    except:
        return {'bid': 0, 'ask': 0, 'mid': 0, 'iv': 0, 'volume': 0}
# ============================================================================
# MAIN RUNNER (ASYNC)
# ============================================================================

async def async_main():
    """Async main entry point"""
    
    try:
        # Initialize analyzer
        print("\n🔄 Initializing portfolio analyzer...")
        analyzer = PortfolioAnalyzer(db_url="sqlite:///portfolio.db")
        
        # Async initialization (broker connection)
        await analyzer.async_init()
        
        # Step 1: Sync from Tastytrade → Database (ASYNC)
        print("\n🔄 Syncing portfolio from Tastytrade...")
        await analyzer.sync_portfolio(portfolio_name="My Trading Portfolio")
        
        # Step 2: Display portfolio summary (from Database - SYNC)
        analyzer.display_portfolio_summary()
        
        # Step 3: Display positions by underlying (from Database - SYNC)
        analyzer.display_positions_by_underlying()
        
        # Step 4: Display trades with legs (from Database - SYNC)
        analyzer.display_trades_with_legs()
        
        # Step 5: Display option chains (from Tastytrade API - ASYNC)
        # await analyzer.display_option_chains()  # Uncomment to see option chains
        
        print("\n✅ Analysis complete!\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error in async_main: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


def main():
    """Entry point - runs the async main"""
    # Run the async main function
    asyncio.run(async_main())


if __name__ == "__main__":
    main()