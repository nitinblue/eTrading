"""
Watchlist Service - Fetch and manage watchlists for screeners.

Sources:
    - TastyTrade public watchlists via SDK
    - User-defined custom watchlists

Watchlists are cached in DB. Refresh from TastyTrade on demand or if stale (>24h).

Usage:
    from trading_cotrader.services.watchlist_service import WatchlistService
    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        svc = WatchlistService(session, broker=broker)
        wl = svc.get_or_fetch("Tom's Watchlist")
        print(wl.symbols)
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging

from sqlalchemy.orm import Session

from trading_cotrader.core.models.recommendation import Watchlist
from trading_cotrader.repositories.watchlist import WatchlistRepository

logger = logging.getLogger(__name__)

# Max age before refreshing from TastyTrade
_STALE_HOURS = 24


class WatchlistService:
    """Fetch, cache, and manage watchlists."""

    def __init__(self, session: Session, broker=None):
        """
        Args:
            session: SQLAlchemy session.
            broker: TastytradeAdapter (authenticated). None = offline mode.
        """
        self.session = session
        self.broker = broker
        self.repo = WatchlistRepository(session)

    def get_or_fetch(self, name: str, force_refresh: bool = False) -> Optional[Watchlist]:
        """
        Get watchlist by name. If from TastyTrade and stale/missing, fetch live.

        Args:
            name: Watchlist name (e.g. "Tom's Watchlist").
            force_refresh: Force re-fetch from TastyTrade.

        Returns:
            Watchlist domain object or None.
        """
        cached = self.repo.get_by_name(name)

        if cached and not force_refresh:
            # Check staleness for TastyTrade lists
            if cached.source == 'tastytrade' and cached.last_refreshed:
                age = datetime.utcnow() - cached.last_refreshed
                if age < timedelta(hours=_STALE_HOURS):
                    return cached
                # Stale — try to refresh
                logger.info(f"Watchlist '{name}' is stale ({age.total_seconds()/3600:.0f}h), refreshing")
            else:
                return cached

        # Try to fetch from TastyTrade
        if self.broker:
            fetched = self._fetch_from_tastytrade(name)
            if fetched:
                return fetched

        # Return cached even if stale (offline fallback)
        if cached:
            logger.warning(f"Using stale cached watchlist '{name}' (no broker)")
            return cached

        return None

    def get_all(self) -> List[Watchlist]:
        """Get all cached watchlists."""
        return self.repo.get_all_watchlists()

    def create_custom(self, name: str, symbols: List[str], description: str = "") -> Optional[Watchlist]:
        """Create a user-defined custom watchlist."""
        wl = Watchlist(
            name=name,
            source='custom',
            symbols=symbols,
            description=description,
            last_refreshed=datetime.utcnow(),
        )
        return self.repo.upsert(wl)

    def list_available_tastytrade(self) -> List[str]:
        """List available TastyTrade public watchlist names."""
        if not self.broker:
            logger.warning("No broker connection — cannot list TastyTrade watchlists")
            return []

        try:
            return self.broker.get_public_watchlists()
        except Exception as e:
            logger.error(f"Failed to list TastyTrade watchlists: {e}")
            return []

    def _fetch_from_tastytrade(self, name: str) -> Optional[Watchlist]:
        """Fetch a public watchlist from TastyTrade and cache it."""
        try:
            wl_data = self.broker.get_public_watchlists(name)
            if not wl_data:
                logger.warning(f"TastyTrade watchlist '{name}' not found")
                return None

            # Extract symbols — PublicWatchlists returns watchlist entries
            symbols = []
            if hasattr(wl_data, 'watchlist_entries'):
                symbols = [e.symbol for e in wl_data.watchlist_entries if hasattr(e, 'symbol')]
            elif isinstance(wl_data, list):
                for item in wl_data:
                    if hasattr(item, 'symbol'):
                        symbols.append(item.symbol)
                    elif hasattr(item, 'watchlist_entries'):
                        symbols.extend(
                            e.symbol for e in item.watchlist_entries if hasattr(e, 'symbol')
                        )

            if not symbols:
                logger.warning(f"No symbols found in TastyTrade watchlist '{name}'")
                return None

            wl = Watchlist(
                name=name,
                source='tastytrade',
                symbols=symbols,
                description=f"TastyTrade public watchlist: {name}",
                last_refreshed=datetime.utcnow(),
            )

            saved = self.repo.upsert(wl)
            if saved:
                logger.info(f"Cached TastyTrade watchlist '{name}' with {len(symbols)} symbols")
            return saved

        except ImportError:
            logger.error("tastytrade SDK not available for watchlist fetch")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch TastyTrade watchlist '{name}': {e}")
            return None
