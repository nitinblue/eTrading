"""
IV Rank Screener — Recommends trades based on implied volatility rank.

Strategy logic:
    IV Rank > 50:  Sell premium (iron condor, strangle, iron butterfly)
    IV Rank < 20:  Buy premium (debit spreads, long straddle)
    IV Rank 20-50: Skip (no edge)

Uses TechnicalAnalysisService for IV rank proxy (realized vol range).
Applies entry filters from risk_config.yaml.
"""

from decimal import Decimal
from typing import List, Optional
import logging

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendedLeg, MarketSnapshot
)
from trading_cotrader.services.screeners.screener_base import ScreenerBase

logger = logging.getLogger(__name__)


class IvRankScreener(ScreenerBase):
    """Screen symbols based on IV rank from TechnicalAnalysisService."""

    name = "IV Rank Screener"
    source = "screener_iv_rank"

    def __init__(self, broker=None, technical_service=None):
        super().__init__(broker, technical_service=technical_service)

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        Screen symbols by IV rank.

        High IV rank → sell premium
        Low IV rank → buy premium
        Middle → skip
        """
        if not self.technical_service:
            logger.info("IV Rank screener requires TechnicalAnalysisService — using mock mode")
            from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService
            self.technical_service = TechnicalAnalysisService(use_mock=True)

        recommendations = []
        expiration = self._get_nearest_monthly_expiration(dte_target=45)

        for symbol in symbols:
            try:
                rec = self._evaluate_symbol(symbol, expiration)
                if rec:
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"IV rank screener failed for {symbol}: {e}")

        logger.info(f"IV Rank screener generated {len(recommendations)} recommendations")
        return recommendations

    def _evaluate_symbol(
        self, symbol: str, expiration: str
    ) -> Optional[Recommendation]:
        """Evaluate a single symbol for IV rank trade."""
        tech_snap = self._get_technical_snapshot(symbol)
        if tech_snap is None:
            return None

        iv_rank = tech_snap.iv_rank
        if iv_rank is None:
            logger.info(f"No IV rank data for {symbol}, skipping")
            return None

        price = tech_snap.current_price
        if not price or price <= 0:
            return None

        # Build market context
        market_ctx = MarketSnapshot(
            underlying_price=price,
            market_trend="iv_rank_based",
        )
        market_ctx = self._enrich_market_context(market_ctx, tech_snap)

        # IV Rank > 50 → sell premium
        if iv_rank > 50:
            return self._recommend_sell_premium(
                symbol, price, iv_rank, tech_snap, expiration, market_ctx
            )
        # IV Rank < 20 → buy premium
        elif iv_rank < 20:
            return self._recommend_buy_premium(
                symbol, price, iv_rank, tech_snap, expiration, market_ctx
            )
        else:
            logger.info(
                f"Skipping {symbol}: IV rank {iv_rank:.0f} in neutral zone (20-50)"
            )
            return None

    def _recommend_sell_premium(
        self,
        symbol: str,
        price: Decimal,
        iv_rank: float,
        tech_snap,
        exp: str,
        ctx: MarketSnapshot,
    ) -> Optional[Recommendation]:
        """High IV rank — sell premium with iron condor."""
        strategy_type = 'iron_condor'

        # Check entry filters
        passed, reason = self._check_entry_filters(strategy_type, tech_snap)
        if not passed:
            logger.info(f"Skipping {symbol} {strategy_type}: {reason}")
            return None

        # Build iron condor
        wing_pct = Decimal('0.06')  # wider wings in high IV
        put_short = _round_strike(price * (1 - wing_pct))
        put_long = _round_strike(put_short - 5)
        call_short = _round_strike(price * (1 + wing_pct))
        call_long = _round_strike(call_short + 5)

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', put_long),
                quantity=1, strike=put_long, option_type='put', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'P', put_short),
                quantity=-1, strike=put_short, option_type='put', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'C', call_short),
                quantity=-1, strike=call_short, option_type='call', expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(symbol, exp, 'C', call_long),
                quantity=1, strike=call_long, option_type='call', expiration=exp,
            ),
        ]

        confidence = 7 if iv_rank > 70 else 6

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type=strategy_type,
            legs=legs,
            market_context=ctx,
            confidence=confidence,
            rationale=(
                f"IV Rank={iv_rank:.0f} (high) — sell premium with iron condor, "
                f"elevated vol likely to revert"
            ),
            risk_category='defined',
        )

    def _recommend_buy_premium(
        self,
        symbol: str,
        price: Decimal,
        iv_rank: float,
        tech_snap,
        exp: str,
        ctx: MarketSnapshot,
    ) -> Optional[Recommendation]:
        """Low IV rank — buy premium with debit vertical spread."""
        # Use directional regime to pick direction
        regime = tech_snap.directional_regime if tech_snap else "F"

        if regime == "U":
            strategy_type = 'vertical_spread'
            option_type = 'C'
            long_strike = _round_strike(price)
            short_strike = _round_strike(price + 10)
            rationale_dir = "bullish"
        elif regime == "D":
            strategy_type = 'vertical_spread'
            option_type = 'P'
            long_strike = _round_strike(price)
            short_strike = _round_strike(price - 10)
            rationale_dir = "bearish"
        else:
            # Flat regime + low IV → skip (no edge)
            logger.info(
                f"Skipping {symbol}: IV rank {iv_rank:.0f} low but flat regime, no directional edge"
            )
            return None

        # Check entry filters
        passed, reason = self._check_entry_filters(strategy_type, tech_snap)
        if not passed:
            logger.info(f"Skipping {symbol} {strategy_type}: {reason}")
            return None

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(
                    symbol, exp, option_type, long_strike
                ),
                quantity=1, strike=long_strike, option_type=option_type.lower(),
                expiration=exp,
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(
                    symbol, exp, option_type, short_strike
                ),
                quantity=-1, strike=short_strike, option_type=option_type.lower(),
                expiration=exp,
            ),
        ]

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type=strategy_type,
            legs=legs,
            market_context=ctx,
            confidence=5,
            rationale=(
                f"IV Rank={iv_rank:.0f} (low) — buy premium with {rationale_dir} "
                f"debit spread, cheap options"
            ),
            risk_category='defined',
        )


def _round_strike(price: Decimal, step: int = 5) -> Decimal:
    """Round price to nearest strike increment."""
    return Decimal(str(round(int(price) / step) * step))
