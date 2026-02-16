"""
LEAPS Entry Screener — Very picky entry for long-term investments.

ALL conditions must be met (AND logic):
    1. Significant correction: price > 10% below 52-week high
    2. Near support: within 3% of SMA(200) or recent swing low
    3. Elevated IV: IV rank > 40

If all 3 met → recommend LEAPS entry:
    - single (deep ITM long call, 6-24 month expiry)
    - diagonal_spread (PMCC — sell short-term, own long-term)

By design, most screening runs produce 0 recommendations. Picky entry.

Usage:
    python -m trading_cotrader.cli.run_screener --screener leaps --symbols AAPL,MSFT --no-broker
"""

from decimal import Decimal
from typing import List, Optional
import logging

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendedLeg, MarketSnapshot
)
from trading_cotrader.services.screeners.screener_base import ScreenerBase

logger = logging.getLogger(__name__)

# LEAPS criteria thresholds
MIN_PCT_FROM_HIGH = -10.0     # Must be at least 10% below 52w high
MAX_DIST_TO_SUPPORT = 0.03    # Within 3% of support level
MIN_IV_RANK = 40.0            # IV rank must be elevated
MIN_DTE = 180                 # At least 6 months
MAX_DTE = 730                 # Up to 2 years


class LeapsEntryScreener(ScreenerBase):
    """
    Screen for LEAPS entries — only on corrections, at support, with elevated IV.
    Very selective. Most runs return 0 recommendations. That's intentional.
    """

    name = "LEAPS Entry Screener"
    source = "screener_leaps"

    def __init__(self, broker=None, technical_service=None):
        super().__init__(broker, technical_service=technical_service)

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """Screen symbols for LEAPS entry opportunities."""
        if not self.technical_service:
            logger.info("LEAPS screener requires TechnicalAnalysisService — using mock mode")
            from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService
            self.technical_service = TechnicalAnalysisService(use_mock=True)

        recommendations = []

        for symbol in symbols:
            try:
                rec = self._evaluate_symbol(symbol)
                if rec:
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"LEAPS screener failed for {symbol}: {e}")

        logger.info(
            f"LEAPS screener: {len(symbols)} symbols evaluated, "
            f"{len(recommendations)} recommendations"
        )
        return recommendations

    def _evaluate_symbol(self, symbol: str) -> Optional[Recommendation]:
        """Evaluate a single symbol for LEAPS entry."""
        tech_snap = self._get_technical_snapshot(symbol)
        if tech_snap is None:
            return None

        price = tech_snap.current_price
        if not price or price <= 0:
            return None

        # === Gate 1: Significant correction (> 10% below 52w high) ===
        if tech_snap.pct_from_52w_high is None:
            logger.info(f"Skipping {symbol}: no 52w high data")
            return None

        if tech_snap.pct_from_52w_high > MIN_PCT_FROM_HIGH:
            logger.info(
                f"Skipping {symbol}: only {tech_snap.pct_from_52w_high:.1f}% "
                f"from high (need <{MIN_PCT_FROM_HIGH}%)"
            )
            return None

        # === Gate 2: Near support (within 3% of SMA 200 or swing low) ===
        support = tech_snap.nearest_support
        if support is None:
            logger.info(f"Skipping {symbol}: no support level identified")
            return None

        dist_to_support = abs(float(price) - float(support)) / float(price)
        if dist_to_support > MAX_DIST_TO_SUPPORT:
            logger.info(
                f"Skipping {symbol}: {dist_to_support:.1%} from support "
                f"(need <{MAX_DIST_TO_SUPPORT:.0%})"
            )
            return None

        # === Gate 3: Elevated IV (IV rank > 40) ===
        iv_rank = tech_snap.iv_rank
        if iv_rank is None:
            logger.info(f"Skipping {symbol}: no IV rank data")
            return None

        if iv_rank < MIN_IV_RANK:
            logger.info(
                f"Skipping {symbol}: IV rank {iv_rank:.0f} "
                f"(need >{MIN_IV_RANK:.0f})"
            )
            return None

        # === ALL 3 GATES PASSED — Generate LEAPS recommendation ===
        logger.info(
            f"LEAPS entry for {symbol}: "
            f"{tech_snap.pct_from_52w_high:.1f}% from high, "
            f"{dist_to_support:.1%} from support, "
            f"IV rank {iv_rank:.0f}"
        )

        # Build market context
        market_ctx = MarketSnapshot(
            underlying_price=price,
            market_trend="correction",
        )
        market_ctx = self._enrich_market_context(market_ctx, tech_snap)

        # Use directional regime to decide specific strategy
        regime = tech_snap.directional_regime or "F"

        if regime == "D":
            # Still falling — use diagonal spread (PMCC) for protection
            return self._recommend_diagonal(symbol, price, tech_snap, market_ctx)
        else:
            # Flat or recovering — deep ITM LEAPS call
            return self._recommend_leaps_call(symbol, price, tech_snap, market_ctx)

    def _recommend_leaps_call(
        self,
        symbol: str,
        price: Decimal,
        tech_snap,
        ctx: MarketSnapshot,
    ) -> Recommendation:
        """Recommend deep ITM LEAPS call."""
        # Target ~180 DTE expiration for LEAPS
        expiration = self._get_nearest_monthly_expiration(dte_target=MIN_DTE)

        # Deep ITM: strike at ~80% of current price (high delta)
        strike = _round_strike(price * Decimal('0.80'))

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(
                    symbol, expiration, 'C', strike
                ),
                quantity=1,
                strike=strike,
                option_type='call',
                expiration=expiration,
                delta_target=Decimal('0.80'),
            ),
        ]

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type='single',
            legs=legs,
            market_context=ctx,
            confidence=7,
            rationale=(
                f"LEAPS entry: {tech_snap.pct_from_52w_high:.1f}% correction, "
                f"near support ${float(tech_snap.nearest_support):.0f}, "
                f"IV rank {tech_snap.iv_rank:.0f} — deep ITM call"
            ),
            risk_category='defined',
        )

    def _recommend_diagonal(
        self,
        symbol: str,
        price: Decimal,
        tech_snap,
        ctx: MarketSnapshot,
    ) -> Recommendation:
        """Recommend diagonal spread (PMCC) — own long-term, sell short-term."""
        # Long leg: ~180 DTE, deep ITM
        long_exp = self._get_nearest_monthly_expiration(dte_target=MIN_DTE)
        long_strike = _round_strike(price * Decimal('0.80'))

        # Short leg: ~45 DTE, OTM
        short_exp = self._get_nearest_monthly_expiration(dte_target=45)
        short_strike = _round_strike(price * Decimal('1.05'))

        legs = [
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(
                    symbol, long_exp, 'C', long_strike
                ),
                quantity=1,
                strike=long_strike,
                option_type='call',
                expiration=long_exp,
                delta_target=Decimal('0.80'),
            ),
            RecommendedLeg(
                streamer_symbol=self._build_option_streamer_symbol(
                    symbol, short_exp, 'C', short_strike
                ),
                quantity=-1,
                strike=short_strike,
                option_type='call',
                expiration=short_exp,
                delta_target=Decimal('0.20'),
            ),
        ]

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type='diagonal_spread',
            legs=legs,
            market_context=ctx,
            confidence=6,
            rationale=(
                f"LEAPS PMCC: {tech_snap.pct_from_52w_high:.1f}% correction, "
                f"still downtrending — diagonal for protection, "
                f"IV rank {tech_snap.iv_rank:.0f}"
            ),
            risk_category='defined',
        )


def _round_strike(price: Decimal, step: int = 5) -> Decimal:
    """Round price to nearest strike increment."""
    return Decimal(str(round(int(price) / step) * step))
