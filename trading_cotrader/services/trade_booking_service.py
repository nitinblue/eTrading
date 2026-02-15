"""
Trade Booking Service - End-to-End WhatIf Trade Lifecycle

Creates a WhatIf trade with live Greeks from DXLink streaming:
    User Input (streamer symbols) → DXLink (Greeks + Quotes)
    → Trade Domain Object → DB (Trade + Event) → Containers → Snapshot → AI/ML

Streamer symbol formats:
    Equity:  "SPY"
    Option:  ".SPY260320P550"  (DXFeed format: .{ticker}{YYMMDD}{P/C}{strike})

Usage:
    python -m trading_cotrader.services.trade_booking_service
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import logging
import re
import uuid

import trading_cotrader.core.models.domain as dm
import trading_cotrader.core.models.events as ev
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.repositories.trade import TradeRepository
from trading_cotrader.repositories.event import EventRepository
from trading_cotrader.repositories.portfolio import PortfolioRepository

logger = logging.getLogger(__name__)

# Regex to parse option streamer symbols: .TICKER YYMMDD P/C STRIKE
_OPTION_SYMBOL_RE = re.compile(
    r'^\.([A-Z]+)(\d{6})([PC])(\d+)$'
)

from trading_cotrader.core.models.strategy_templates import get_strategy_type_from_string


@dataclass
class LegInput:
    """Input for a single leg of a trade."""
    streamer_symbol: str    # ".SPY260320P550" or "SPY"
    quantity: int           # positive=buy, negative=sell


@dataclass
class LegResult:
    """Result details for a single leg."""
    streamer_symbol: str
    underlying: str
    asset_type: str
    option_type: Optional[str]
    strike: Optional[Decimal]
    expiration: Optional[date]
    quantity: int
    side: str
    mid_price: Decimal
    bid: Decimal
    ask: Decimal
    per_contract_greeks: Dict[str, float]
    position_greeks: Dict[str, float]


@dataclass
class TradeBookingResult:
    """Result of a trade booking operation."""
    success: bool
    trade_id: str = ""
    underlying: str = ""
    strategy_type: str = ""
    legs: List[LegResult] = field(default_factory=list)
    total_greeks: Dict[str, float] = field(default_factory=dict)
    entry_price: Decimal = Decimal('0')
    event_id: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'trade_id': self.trade_id,
            'underlying': self.underlying,
            'strategy_type': self.strategy_type,
            'legs_count': len(self.legs),
            'total_greeks': self.total_greeks,
            'entry_price': float(self.entry_price),
            'event_id': self.event_id,
            'error': self.error,
        }


class TradeBookingService:
    """
    End-to-end WhatIf trade booking with live market data.

    Flow:
        1. Parse streamer symbols → determine equity vs option
        2. Fetch Greeks + Quotes from DXLink via broker adapter
        3. Build Trade domain object with legs and aggregated Greeks
        4. Persist Trade + Event to DB
        5. Refresh containers for UI
        6. Capture snapshot for analytics
        7. Feed AI/ML pipeline
    """

    def __init__(self, broker, container_manager=None):
        """
        Args:
            broker: TastytradeAdapter instance (authenticated)
            container_manager: Optional ContainerManager for UI updates
        """
        self.broker = broker
        self.container_manager = container_manager

    def book_whatif_trade(
        self,
        underlying: str,
        strategy_type: str,
        legs: List[LegInput],
        notes: str = "",
        rationale: str = "",
        confidence: int = 5,
        portfolio_name: Optional[str] = None,
    ) -> TradeBookingResult:
        """
        Book a WhatIf trade end-to-end.

        Args:
            underlying: Ticker symbol (e.g., "SPY")
            strategy_type: Strategy name (e.g., "vertical_spread")
            legs: List of LegInput with streamer symbols and quantities
            notes: Trade notes
            rationale: Why this trade (for AI learning)
            confidence: Confidence level 1-10
            portfolio_name: Optional portfolio config name (e.g., "core_holdings").
                           If provided, validates strategy is allowed and routes
                           the trade to that portfolio.

        Returns:
            TradeBookingResult with full trade details
        """
        try:
            # Step 0: Validate portfolio permissions if portfolio_name specified
            if portfolio_name:
                from trading_cotrader.services.portfolio_manager import PortfolioManager
                with session_scope() as session:
                    pm = PortfolioManager(session)
                    check = pm.validate_trade_for_portfolio(portfolio_name, strategy_type)
                    if not check['allowed']:
                        return TradeBookingResult(
                            success=False, error=check['reason']
                        )

            # Step 1: Collect streamer symbols
            option_symbols = []
            equity_symbols = []
            for leg in legs:
                if leg.streamer_symbol.startswith('.'):
                    option_symbols.append(leg.streamer_symbol)
                else:
                    equity_symbols.append(leg.streamer_symbol)

            all_symbols = option_symbols + equity_symbols
            logger.info(f"Booking WhatIf: {underlying} {strategy_type} "
                        f"({len(option_symbols)} options, {len(equity_symbols)} equities)")

            # Step 2: Fetch market data from DXLink
            greeks_map, quotes_map = self._fetch_market_data(option_symbols, equity_symbols)

            # Step 3: Build Trade domain object
            trade, leg_results = self._build_trade(
                underlying, strategy_type, legs, greeks_map, quotes_map, notes
            )

            # Step 4: Persist to DB
            event = self._create_event(trade, strategy_type, rationale, confidence)
            self._persist_trade(trade, event, portfolio_name=portfolio_name)

            # Step 5: Update containers
            if self.container_manager:
                self._refresh_containers()

            # Step 6-7: Snapshot + ML
            self._update_snapshot_and_ml(trade)

            total_greeks = {
                'delta': float(trade.entry_greeks.delta),
                'gamma': float(trade.entry_greeks.gamma),
                'theta': float(trade.entry_greeks.theta),
                'vega': float(trade.entry_greeks.vega),
            }

            logger.info(f"WhatIf trade booked: {trade.id}")
            logger.info(f"  Entry: ${trade.entry_price:.2f}  "
                        f"Delta={total_greeks['delta']:.2f}  "
                        f"Theta={total_greeks['theta']:.2f}")

            return TradeBookingResult(
                success=True,
                trade_id=trade.id,
                underlying=underlying,
                strategy_type=strategy_type,
                legs=leg_results,
                total_greeks=total_greeks,
                entry_price=trade.entry_price,
                event_id=event.event_id,
            )

        except Exception as e:
            logger.error(f"Failed to book WhatIf trade: {e}")
            logger.exception("Full trace:")
            return TradeBookingResult(success=False, error=str(e))

    # =========================================================================
    # Internal methods
    # =========================================================================

    def _fetch_market_data(
        self,
        option_symbols: List[str],
        equity_symbols: List[str],
    ) -> Tuple[Dict[str, dm.Greeks], Dict[str, Dict]]:
        """
        Fetch Greeks and quotes from DXLink.

        Returns:
            (greeks_map, quotes_map) where:
            - greeks_map: {symbol: dm.Greeks} (per-contract)
            - quotes_map: {symbol: {'bid': float, 'ask': float}}
        """
        greeks_map: Dict[str, dm.Greeks] = {}
        quotes_map: Dict[str, Dict] = {}

        # Fetch option Greeks via DXLink
        if option_symbols:
            logger.info(f"Fetching Greeks for {len(option_symbols)} options: {option_symbols}")
            greeks_map = self.broker._run_async(
                self.broker._fetch_greeks_via_dxlink(option_symbols)
            )
            logger.info(f"Got Greeks for {len(greeks_map)}/{len(option_symbols)} symbols")

            # Fetch quotes for bid/ask
            quotes_map = self._fetch_quotes(option_symbols)
            logger.info(f"Got quotes for {len(quotes_map)}/{len(option_symbols)} symbols")

        # Equity symbols don't need Greeks from DXLink (delta = quantity)
        if equity_symbols:
            equity_quotes = self._fetch_quotes(equity_symbols)
            quotes_map.update(equity_quotes)

        return greeks_map, quotes_map

    def _fetch_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch bid/ask quotes via DXLink streaming."""
        import asyncio
        from tastytrade.streamer import DXLinkStreamer
        from tastytrade.dxfeed import Quote as DXQuote

        async def _stream_quotes() -> Dict[str, Dict]:
            quotes = {}
            try:
                async with DXLinkStreamer(self.broker.data_session) as streamer:
                    await streamer.subscribe(DXQuote, symbols)
                    symbols_needed = set(symbols)
                    timeout_seconds = 5

                    start_time = asyncio.get_event_loop().time()
                    while symbols_needed and (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                        try:
                            event = await asyncio.wait_for(
                                streamer.get_event(DXQuote),
                                timeout=2.0
                            )
                            sym = event.event_symbol
                            if sym in symbols_needed:
                                quotes[sym] = {
                                    'bid': float(event.bid_price or 0),
                                    'ask': float(event.ask_price or 0),
                                }
                                symbols_needed.remove(sym)
                        except asyncio.TimeoutError:
                            continue
            except Exception as e:
                logger.warning(f"Quote fetch error: {e}")
            return quotes

        try:
            return self.broker._run_async(_stream_quotes())
        except Exception as e:
            logger.warning(f"Failed to fetch quotes: {e}")
            return {}

    def _parse_streamer_symbol(self, symbol: str) -> dm.Symbol:
        """
        Parse a streamer symbol into a domain Symbol object.

        Option: ".SPY260320P550" → Symbol(SPY, OPTION, PUT, 550, 2026-03-20)
        Equity: "SPY" → Symbol(SPY, EQUITY)
        """
        if symbol.startswith('.'):
            match = _OPTION_SYMBOL_RE.match(symbol)
            if not match:
                raise ValueError(f"Invalid option streamer symbol: {symbol}")

            ticker, exp_str, opt_type_char, strike_str = match.groups()
            exp_date = datetime.strptime(exp_str, '%y%m%d').date()
            option_type = dm.OptionType.CALL if opt_type_char == 'C' else dm.OptionType.PUT
            strike = Decimal(strike_str)

            return dm.Symbol(
                ticker=ticker,
                asset_type=dm.AssetType.OPTION,
                option_type=option_type,
                strike=strike,
                expiration=exp_date,
                multiplier=100,
            )
        else:
            return dm.Symbol(
                ticker=symbol,
                asset_type=dm.AssetType.EQUITY,
                multiplier=1,
            )

    def _build_trade(
        self,
        underlying: str,
        strategy_type: str,
        legs: List[LegInput],
        greeks_map: Dict[str, dm.Greeks],
        quotes_map: Dict[str, Dict],
        notes: str,
    ) -> Tuple[dm.Trade, List[LegResult]]:
        """Build Trade domain object from inputs + market data."""
        trade_id = str(uuid.uuid4())
        domain_legs = []
        leg_results = []
        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')
        net_entry_price = Decimal('0')

        for i, leg_input in enumerate(legs):
            symbol = self._parse_streamer_symbol(leg_input.streamer_symbol)
            qty = leg_input.quantity
            is_short = qty < 0
            multiplier = symbol.multiplier

            # Get quote
            quote = quotes_map.get(leg_input.streamer_symbol, {})
            bid = Decimal(str(quote.get('bid', 0) or 0))
            ask = Decimal(str(quote.get('ask', 0) or 0))
            mid_price = (bid + ask) / 2 if (bid and ask) else Decimal('0')

            # Get per-contract Greeks
            if symbol.is_option:
                greeks = greeks_map.get(leg_input.streamer_symbol)
                if greeks:
                    leg_delta = greeks.delta
                    leg_gamma = greeks.gamma
                    leg_theta = greeks.theta
                    leg_vega = greeks.vega
                else:
                    logger.warning(f"No Greeks for {leg_input.streamer_symbol}, using zeros")
                    leg_delta = leg_gamma = leg_theta = leg_vega = Decimal('0')
            else:
                # Equity: delta = 1 per share, no other Greeks
                leg_delta = Decimal('1')
                leg_gamma = leg_theta = leg_vega = Decimal('0')

            # Position Greeks = per_contract × qty × multiplier
            pos_delta = leg_delta * qty * multiplier
            pos_gamma = leg_gamma * abs(qty) * multiplier
            pos_theta = leg_theta * qty * multiplier
            pos_vega = leg_vega * qty * multiplier

            total_delta += pos_delta
            total_gamma += pos_gamma
            total_theta += pos_theta
            total_vega += pos_vega

            # Net entry: credit (short) is positive, debit (long) is negative
            leg_cost = mid_price * abs(qty) * multiplier
            net_entry_price += leg_cost if is_short else -leg_cost

            # Build domain Leg
            per_contract_greeks = dm.Greeks(
                delta=leg_delta, gamma=leg_gamma,
                theta=leg_theta, vega=leg_vega,
            )
            domain_leg = dm.Leg(
                id=f"{trade_id}_leg_{i}",
                symbol=symbol,
                quantity=qty,
                side=dm.OrderSide.SELL_TO_OPEN if is_short else dm.OrderSide.BUY_TO_OPEN,
                entry_price=mid_price,
                current_price=mid_price,
                entry_greeks=per_contract_greeks,
                current_greeks=per_contract_greeks,
            )
            domain_legs.append(domain_leg)

            leg_results.append(LegResult(
                streamer_symbol=leg_input.streamer_symbol,
                underlying=symbol.ticker,
                asset_type=symbol.asset_type.value,
                option_type=symbol.option_type.value if symbol.option_type else None,
                strike=symbol.strike,
                expiration=symbol.expiration if symbol.expiration else None,
                quantity=qty,
                side='sell' if is_short else 'buy',
                mid_price=mid_price,
                bid=bid,
                ask=ask,
                per_contract_greeks={
                    'delta': float(leg_delta), 'gamma': float(leg_gamma),
                    'theta': float(leg_theta), 'vega': float(leg_vega),
                },
                position_greeks={
                    'delta': float(pos_delta), 'gamma': float(pos_gamma),
                    'theta': float(pos_theta), 'vega': float(pos_vega),
                },
            ))

            logger.info(
                f"  Leg {i}: {leg_input.streamer_symbol} qty={qty} "
                f"mid=${mid_price:.2f} Δ={pos_delta:.2f} Θ={pos_theta:.2f}"
            )

        # Build aggregated Greeks
        trade_greeks = dm.Greeks(
            delta=total_delta, gamma=total_gamma,
            theta=total_theta, vega=total_vega,
        )

        # Resolve strategy type
        st = get_strategy_type_from_string(strategy_type)

        trade = dm.Trade.create_what_if(
            underlying=underlying,
            strategy_type=st,
            legs=domain_legs,
            entry_price=net_entry_price,
            current_price=net_entry_price,
            entry_greeks=trade_greeks,
            current_greeks=trade_greeks,
            notes=notes,
        )
        # Override the auto-generated ID so we can track it
        object.__setattr__(trade, 'id', trade_id) if hasattr(trade, '__dataclass_fields__') else None
        trade.id = trade_id

        return trade, leg_results

    def _create_event(
        self,
        trade: dm.Trade,
        strategy_type: str,
        rationale: str,
        confidence: int,
    ) -> ev.TradeEvent:
        """Create a TradeEvent for AI learning."""
        return ev.TradeEvent(
            event_type=ev.EventType.TRADE_OPENED,
            trade_id=trade.id,
            strategy_type=strategy_type,
            underlying_symbol=trade.underlying_symbol,
            entry_delta=trade.entry_greeks.delta,
            entry_gamma=trade.entry_greeks.gamma,
            entry_theta=trade.entry_greeks.theta,
            entry_vega=trade.entry_greeks.vega,
            net_credit_debit=trade.entry_price,
            decision_context=ev.DecisionContext(
                rationale=rationale or trade.notes,
                confidence_level=confidence,
            ),
            tags=['what_if', strategy_type],
        )

    def _persist_trade(
        self,
        trade: dm.Trade,
        event: ev.TradeEvent,
        portfolio_name: Optional[str] = None,
    ) -> None:
        """Save trade and event to database."""
        with session_scope() as session:
            trade_repo = TradeRepository(session)
            event_repo = EventRepository(session)
            portfolio_repo = PortfolioRepository(session)

            # Route to named portfolio if specified, otherwise default what-if
            if portfolio_name:
                target_portfolio = portfolio_repo.get_by_account(
                    broker='cotrader', account_id=portfolio_name
                )
                if not target_portfolio:
                    logger.warning(
                        f"Portfolio '{portfolio_name}' not found, falling back to default what-if"
                    )
                    target_portfolio = None

            if not portfolio_name or not target_portfolio:
                target_portfolio = portfolio_repo.get_by_account(
                    broker='whatif', account_id='whatif'
                )
                if not target_portfolio:
                    target_portfolio = dm.Portfolio(
                        name="What-If Portfolio",
                        broker="whatif",
                        account_id="whatif",
                    )
                    target_portfolio = portfolio_repo.create_from_domain(target_portfolio)

            # Save trade
            created = trade_repo.create_from_domain(trade, target_portfolio.id)
            if not created:
                raise RuntimeError(f"Failed to save trade {trade.id} to database")
            logger.info(f"Saved trade to DB: {trade.id}")

            # Save event
            event_repo.create_from_domain(event)
            logger.info(f"Saved event to DB: {event.event_id}")

    def _refresh_containers(self) -> None:
        """Refresh containers from database for UI updates."""
        try:
            with session_scope() as session:
                self.container_manager.load_from_repositories(session)
            logger.info("Containers refreshed")
        except Exception as e:
            logger.warning(f"Container refresh failed: {e}")

    def _update_snapshot_and_ml(self, trade: dm.Trade) -> None:
        """Capture snapshot and feed ML pipeline."""
        try:
            with session_scope() as session:
                # Snapshot
                from trading_cotrader.services.snapshot_service import SnapshotService
                snapshot_svc = SnapshotService(session)

                portfolio_repo = PortfolioRepository(session)
                whatif_portfolio = portfolio_repo.get_by_account(
                    broker='whatif', account_id='whatif'
                )
                if whatif_portfolio:
                    snapshot_svc.capture_daily_snapshot(
                        portfolio=whatif_portfolio,
                        positions=[],
                        trades=[trade],
                    )
                    logger.info("Snapshot captured for WhatIf portfolio")
        except Exception as e:
            logger.warning(f"Snapshot capture failed (non-blocking): {e}")

        try:
            # ML pipeline
            from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline
            with session_scope() as session:
                ml_pipeline = MLDataPipeline(session)
                ml_pipeline.accumulate_training_data()
                logger.info("ML pipeline updated")
        except Exception as e:
            logger.warning(f"ML pipeline update failed (non-blocking): {e}")


# =============================================================================
# Standalone test - run with: python -m trading_cotrader.services.trade_booking_service
# =============================================================================

def main():
    """Test the trade booking service with a live broker connection."""
    import sys
    from pathlib import Path

    # Ensure project root is on path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from trading_cotrader.config.settings import setup_logging
    setup_logging()

    print("=" * 70)
    print("  TRADE BOOKING SERVICE - Standalone Test")
    print("=" * 70)
    print()

    # Step 1: Connect to broker
    print("[1] Connecting to broker...")
    from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
    broker = TastytradeAdapter(is_paper=True)
    if not broker.authenticate():
        print("  FAILED: Could not authenticate with TastyTrade")
        return 1
    print("  Connected!")
    print()

    # Step 2: Create the service
    service = TradeBookingService(broker=broker)

    # Step 3: Book a sample SPY put credit spread
    print("[2] Booking WhatIf: SPY Put Credit Spread...")
    print("    Sell .SPY260320P550, Buy .SPY260320P540")
    print()

    result = service.book_whatif_trade(
        underlying="SPY",
        strategy_type="vertical_spread",
        legs=[
            LegInput(streamer_symbol=".SPY260320P682", quantity=-1),
            LegInput(streamer_symbol=".SPY260320P677", quantity=1),
        ],
        notes="Test put credit spread via trade booking service",
        rationale="Testing end-to-end WhatIf booking flow",
        confidence=7,
    )

    # Step 4: Display results
    print()
    print("-" * 70)
    if result.success:
        print(f"  SUCCESS: Trade booked!")
        print(f"  Trade ID:  {result.trade_id}")
        print(f"  Event ID:  {result.event_id}")
        print(f"  Strategy:  {result.strategy_type}")
        print(f"  Entry:     ${result.entry_price:.2f}")
        print()
        print(f"  Total Greeks:")
        print(f"    Delta: {result.total_greeks.get('delta', 0):.4f}")
        print(f"    Gamma: {result.total_greeks.get('gamma', 0):.4f}")
        print(f"    Theta: {result.total_greeks.get('theta', 0):.4f}")
        print(f"    Vega:  {result.total_greeks.get('vega', 0):.4f}")
        print()
        print("  Legs:")
        for i, leg in enumerate(result.legs):
            print(f"    [{i}] {leg.streamer_symbol}  qty={leg.quantity}  "
                  f"mid=${leg.mid_price:.2f}  "
                  f"bid=${leg.bid:.2f}  ask=${leg.ask:.2f}")
            print(f"        Per-contract: Δ={leg.per_contract_greeks['delta']:.4f}  "
                  f"Θ={leg.per_contract_greeks['theta']:.4f}")
            print(f"        Position:     Δ={leg.position_greeks['delta']:.2f}  "
                  f"Θ={leg.position_greeks['theta']:.2f}")
    else:
        print(f"  FAILED: {result.error}")

    print("-" * 70)
    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
