"""
IV Rank Screener — Recommends trades based on implied volatility rank.

Strategy logic:
    IV Rank > 50:  Sell premium (short strangles, iron condors)
    IV Rank < 20:  Buy premium (long straddles, debit spreads)
    IV Rank 20-50: Skip (no edge)

STATUS: Stub — requires IV rank data from broker or historical vol service.
"""

from decimal import Decimal
from typing import List, Optional
import logging

from trading_cotrader.core.models.recommendation import Recommendation, MarketSnapshot
from trading_cotrader.services.screeners.screener_base import ScreenerBase

logger = logging.getLogger(__name__)


class IvRankScreener(ScreenerBase):
    """Screen symbols based on IV rank. STUB — needs IV rank data."""

    name = "IV Rank Screener"
    source = "screener_iv_rank"

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        Screen symbols by IV rank.

        Currently returns empty — needs IV rank data source.
        """
        logger.info(f"IV Rank screener called with {len(symbols)} symbols (STUB)")
        # TODO: Implement when IV rank data is available
        # Need: historical IV data to compute rank, or broker API for IV rank
        return []
