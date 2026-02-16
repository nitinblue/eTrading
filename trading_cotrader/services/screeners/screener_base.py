"""
Screener Base Class — Abstract interface for all screeners.

Each screener:
    1. Takes a list of symbols (from a watchlist)
    2. Evaluates market conditions per symbol
    3. Returns a list of Recommendation objects

Screeners do NOT book trades. They only generate recommendations.
The RecommendationService handles the accept/reject lifecycle.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional
import logging

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendedLeg, MarketSnapshot
)

logger = logging.getLogger(__name__)


class ScreenerBase(ABC):
    """Abstract base class for all screeners."""

    # Subclass must set these
    name: str = "base_screener"
    source: str = "manual"  # TradeSource enum value

    def __init__(self, broker=None):
        """
        Args:
            broker: TastytradeAdapter (authenticated). None = mock mode.
        """
        self.broker = broker

    @abstractmethod
    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        Screen a list of symbols and generate recommendations.

        Args:
            symbols: List of underlying ticker symbols.

        Returns:
            List of Recommendation objects.
        """
        pass

    def get_market_context(self, symbol: str) -> MarketSnapshot:
        """
        Get current market context for a symbol.
        Override in subclass for live data.

        Returns:
            MarketSnapshot with current conditions.
        """
        return MarketSnapshot(underlying_price=Decimal('0'))

    def _build_option_streamer_symbol(
        self,
        ticker: str,
        expiration_str: str,
        option_type: str,
        strike: Decimal,
    ) -> str:
        """
        Build DXLink streamer symbol for an option.

        Args:
            ticker: Underlying ticker (e.g. "SPY")
            expiration_str: YYMMDD format (e.g. "260320")
            option_type: "C" or "P"
            strike: Strike price

        Returns:
            Streamer symbol (e.g. ".SPY260320P550")
        """
        strike_str = str(int(strike))
        return f".{ticker}{expiration_str}{option_type}{strike_str}"

    def _get_nearest_monthly_expiration(self, dte_target: int = 45) -> str:
        """
        Get the nearest monthly options expiration as YYMMDD string.
        Targets approximately `dte_target` days out.

        Returns:
            YYMMDD formatted expiration string.
        """
        from datetime import datetime, timedelta
        import calendar

        target_date = datetime.utcnow() + timedelta(days=dte_target)

        # Find 3rd Friday of the target month
        year = target_date.year
        month = target_date.month
        cal = calendar.Calendar()
        fridays = [
            d for d in cal.itermonthdates(year, month)
            if d.weekday() == 4 and d.month == month
        ]
        if len(fridays) >= 3:
            third_friday = fridays[2]
        else:
            third_friday = fridays[-1]

        # If third friday is in the past, go to next month
        if third_friday < target_date.date():
            month += 1
            if month > 12:
                month = 1
                year += 1
            fridays = [
                d for d in cal.Calendar().itermonthdates(year, month)
                if d.weekday() == 4 and d.month == month
            ]
            third_friday = fridays[2] if len(fridays) >= 3 else fridays[-1]

        return third_friday.strftime('%y%m%d')
