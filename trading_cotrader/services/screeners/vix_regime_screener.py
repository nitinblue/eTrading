"""
VIX Regime Screener — Recommends trades based on VIX level.

Strategy logic:
    VIX < 15 (Low vol):     Sell premium — Iron Condor, 16-delta wings, 30-45 DTE
    VIX 15-25 (Normal):     Neutral — Iron Butterfly or short straddle, ATM, 30-45 DTE
    VIX > 25 (High vol):    Buy vol or defined risk — Calendar spread, 45-60 DTE

Uses DXLink for VIX quote. Strike selection uses delta targets
(actual delta-based selection requires live option chain; falls back
to percentage-of-price estimation when no broker).
"""

from decimal import Decimal
from typing import List, Optional
import logging

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendedLeg, MarketSnapshot
)
from trading_cotrader.services.screeners.screener_base import ScreenerBase

logger = logging.getLogger(__name__)


class VixRegimeScreener(ScreenerBase):
    """Screen symbols based on VIX regime."""

    name = "VIX Regime Screener"
    source = "screener_vix"

    def __init__(self, broker=None, mock_vix: Optional[Decimal] = None):
        """
        Args:
            broker: TastytradeAdapter (authenticated). None = mock mode.
            mock_vix: Override VIX value for testing.
        """
        super().__init__(broker)
        self.mock_vix = mock_vix
        self._vix_level: Optional[Decimal] = None

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        Screen each symbol and generate recommendations based on VIX regime.

        Args:
            symbols: List of underlying tickers to screen.

        Returns:
            List of Recommendation objects.
        """
        vix = self._get_vix()
        if vix is None:
            logger.warning("Could not determine VIX level, skipping screen")
            return []

        self._vix_level = vix
        regime = self._classify_regime(vix)
        logger.info(f"VIX={vix:.1f} → Regime: {regime}")

        recommendations = []
        expiration = self._get_nearest_monthly_expiration(dte_target=45)

        for symbol in symbols:
            try:
                rec = self._generate_recommendation(symbol, vix, regime, expiration)
                if rec:
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"Failed to generate recommendation for {symbol}: {e}")

        logger.info(f"VIX screener generated {len(recommendations)} recommendations")
        return recommendations

    def _get_vix(self) -> Optional[Decimal]:
        """Get current VIX level."""
        if self.mock_vix is not None:
            return self.mock_vix

        if not self.broker:
            logger.warning("No broker — using mock VIX=18")
            return Decimal('18')

        try:
            # Fetch VIX via DXLink quote
            import asyncio
            from tastytrade.streamer import DXLinkStreamer
            from tastytrade.dxfeed import Quote as DXQuote

            async def _get_vix_quote():
                async with DXLinkStreamer(self.broker.data_session) as streamer:
                    await streamer.subscribe(DXQuote, ['VIX'])
                    event = await asyncio.wait_for(
                        streamer.get_event(DXQuote), timeout=5.0
                    )
                    mid = ((event.bid_price or 0) + (event.ask_price or 0)) / 2
                    return Decimal(str(mid))

            return self.broker._run_async(_get_vix_quote())
        except Exception as e:
            logger.error(f"Failed to fetch VIX: {e}")
            return None

    def _classify_regime(self, vix: Decimal) -> str:
        """Classify VIX into a regime."""
        if vix < 15:
            return 'low_vol'
        elif vix <= 25:
            return 'normal'
        else:
            return 'high_vol'

    def _generate_recommendation(
        self,
        symbol: str,
        vix: Decimal,
        regime: str,
        expiration: str,
    ) -> Optional[Recommendation]:
        """Generate a recommendation for a single symbol based on regime."""

        # Get approximate underlying price for strike estimation
        underlying_price = self._get_underlying_price(symbol)
        if not underlying_price or underlying_price <= 0:
            return None

        market_ctx = MarketSnapshot(
            vix=vix,
            underlying_price=underlying_price,
            market_trend=regime,
        )

        if regime == 'low_vol':
            return self._recommend_iron_condor(symbol, underlying_price, expiration, market_ctx)
        elif regime == 'normal':
            return self._recommend_iron_butterfly(symbol, underlying_price, expiration, market_ctx)
        else:  # high_vol
            return self._recommend_calendar_spread(symbol, underlying_price, expiration, market_ctx)

    def _recommend_iron_condor(
        self, symbol: str, price: Decimal, exp: str, ctx: MarketSnapshot
    ) -> Recommendation:
        """Low vol: Sell iron condor with ~16-delta wings."""
        # Estimate 16-delta strikes: ~1 std dev out (~5-7% for 30-45 DTE in low vol)
        wing_pct = Decimal('0.05')
        put_short = _round_strike(price * (1 - wing_pct))
        put_long = _round_strike(put_short - 5)
        call_short = _round_strike(price * (1 + wing_pct))
        call_long = _round_strike(call_short + 5)

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', put_long),
                quantity=1, delta_target=Decimal('0.10'), strike=put_long, option_type='put',
                expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', put_short),
                quantity=-1, delta_target=Decimal('0.16'), strike=put_short, option_type='put',
                expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'C', call_short),
                quantity=-1, delta_target=Decimal('0.16'), strike=call_short, option_type='call',
                expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'C', call_long),
                quantity=1, delta_target=Decimal('0.10'), strike=call_long, option_type='call',
                expiration=exp,
            ),
        ]

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type='iron_condor',
            legs=legs,
            market_context=ctx,
            confidence=7,
            rationale=f"VIX={ctx.vix:.1f} (low vol) — sell premium with iron condor, ~16-delta wings",
            risk_category='defined',
        )

    def _recommend_iron_butterfly(
        self, symbol: str, price: Decimal, exp: str, ctx: MarketSnapshot
    ) -> Recommendation:
        """Normal vol: Sell iron butterfly at ATM."""
        atm = _round_strike(price)
        wing = Decimal('10')

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', atm - wing),
                quantity=1, strike=atm - wing, option_type='put', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', atm),
                quantity=-1, strike=atm, option_type='put', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'C', atm),
                quantity=-1, strike=atm, option_type='call', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'C', atm + wing),
                quantity=1, strike=atm, option_type='call', expiration=exp,
            ),
        ]

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type='iron_butterfly',
            legs=legs,
            market_context=ctx,
            confidence=6,
            rationale=f"VIX={ctx.vix:.1f} (normal) — sell ATM iron butterfly for theta",
            risk_category='defined',
        )

    def _recommend_calendar_spread(
        self, symbol: str, price: Decimal, exp: str, ctx: MarketSnapshot
    ) -> Recommendation:
        """High vol: Buy calendar spread (sell near, buy far)."""
        atm = _round_strike(price)

        # Near-term = exp (45 DTE), far-term = ~75 DTE
        far_exp = self._get_nearest_monthly_expiration(dte_target=75)

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', atm),
                quantity=-1, strike=atm, option_type='put', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, far_exp, 'P', atm),
                quantity=1, strike=atm, option_type='put', expiration=far_exp,
            ),
        ]

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type='calendar_spread',
            legs=legs,
            market_context=ctx,
            confidence=5,
            rationale=f"VIX={ctx.vix:.1f} (high vol) — buy calendar spread, expect vol mean reversion",
            risk_category='defined',
        )

    def _get_underlying_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price for an underlying."""
        if not self.broker:
            # Mock prices for common symbols
            mock_prices = {
                'SPY': Decimal('590'), 'QQQ': Decimal('510'),
                'IWM': Decimal('220'), 'AAPL': Decimal('240'),
                'MSFT': Decimal('430'), 'AMZN': Decimal('210'),
                'GOOGL': Decimal('175'), 'TSLA': Decimal('340'),
                'NVDA': Decimal('135'), 'META': Decimal('590'),
            }
            return mock_prices.get(symbol, Decimal('100'))

        try:
            import asyncio
            from tastytrade.streamer import DXLinkStreamer
            from tastytrade.dxfeed import Quote as DXQuote

            async def _get_quote():
                async with DXLinkStreamer(self.broker.data_session) as streamer:
                    await streamer.subscribe(DXQuote, [symbol])
                    event = await asyncio.wait_for(
                        streamer.get_event(DXQuote), timeout=5.0
                    )
                    mid = ((event.bid_price or 0) + (event.ask_price or 0)) / 2
                    return Decimal(str(mid))

            return self.broker._run_async(_get_quote())
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return None


def _round_strike(price: Decimal, step: int = 5) -> Decimal:
    """Round price to nearest strike increment."""
    return Decimal(str(round(int(price) / step) * step))
