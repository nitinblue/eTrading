"""
Earnings Calendar Service — Fetches upcoming earnings dates via yfinance.

Provides days-to-earnings for scenario screeners (earnings IV crush).
In-memory cache with 24h TTL. No DB table needed — earnings dates are
transient and yfinance is the live source.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours


class EarningsCalendarService:
    """Fetches upcoming earnings dates via yfinance."""

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self._cache: Dict[str, Tuple[datetime, Optional[date]]] = {}

    def get_days_to_earnings(self, symbol: str) -> Optional[int]:
        """
        Days until next earnings for a symbol.

        Returns:
            Number of calendar days, or None if unknown.
        """
        next_date = self._get_next_earnings_date(symbol)
        if next_date is None:
            return None
        delta = (next_date - date.today()).days
        return delta if delta >= 0 else None

    def get_symbols_with_upcoming_earnings(
        self, symbols: List[str], days_ahead: int = 7
    ) -> List[str]:
        """
        Filter symbols to those with earnings in the next N days.

        Args:
            symbols: List of tickers.
            days_ahead: Look-ahead window in days.

        Returns:
            Filtered list of symbols with upcoming earnings.
        """
        result = []
        for symbol in symbols:
            days = self.get_days_to_earnings(symbol)
            if days is not None and 0 <= days <= days_ahead:
                result.append(symbol)
        return result

    def _get_next_earnings_date(self, symbol: str) -> Optional[date]:
        """Fetch next earnings date, with caching."""
        now = datetime.utcnow()

        # Check cache
        if symbol in self._cache:
            cached_at, cached_date = self._cache[symbol]
            if (now - cached_at).total_seconds() < _CACHE_TTL:
                return cached_date

        if self.use_mock:
            # Mock: no upcoming earnings
            self._cache[symbol] = (now, None)
            return None

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            if cal is None or cal.empty:
                self._cache[symbol] = (now, None)
                return None

            # yfinance calendar returns a DataFrame or dict
            # Look for 'Earnings Date' column/key
            earnings_date = None
            if hasattr(cal, 'loc'):
                # DataFrame format
                if 'Earnings Date' in cal.index:
                    val = cal.loc['Earnings Date']
                    if hasattr(val, 'iloc'):
                        val = val.iloc[0]
                    if hasattr(val, 'date'):
                        earnings_date = val.date()
                    elif isinstance(val, str):
                        earnings_date = datetime.strptime(val, '%Y-%m-%d').date()
            elif isinstance(cal, dict):
                ed = cal.get('Earnings Date', [])
                if ed:
                    val = ed[0] if isinstance(ed, list) else ed
                    if hasattr(val, 'date'):
                        earnings_date = val.date()

            self._cache[symbol] = (now, earnings_date)
            return earnings_date

        except Exception as e:
            logger.debug(f"Could not fetch earnings for {symbol}: {e}")
            self._cache[symbol] = (now, None)
            return None
