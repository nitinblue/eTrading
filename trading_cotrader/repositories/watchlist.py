"""
Watchlist Repository - CRUD for watchlists.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from trading_cotrader.repositories.base import BaseRepository
from trading_cotrader.core.database.schema import WatchlistORM
from trading_cotrader.core.models.recommendation import Watchlist

logger = logging.getLogger(__name__)


class WatchlistRepository(BaseRepository[Watchlist, WatchlistORM]):
    """Repository for Watchlist entities."""

    def __init__(self, session: Session):
        super().__init__(session, WatchlistORM)

    def create_from_domain(self, wl: Watchlist) -> Optional[Watchlist]:
        """Create watchlist from domain model."""
        try:
            orm = WatchlistORM(
                id=wl.id,
                name=wl.name,
                source=wl.source,
                symbols=wl.symbols,
                description=wl.description,
                created_at=wl.created_at,
                last_refreshed=wl.last_refreshed,
            )
            created = self.create(orm)
            return self.to_domain(created) if created else None
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating watchlist: {e}")
            return None

    def get_by_name(self, name: str, source: Optional[str] = None) -> Optional[Watchlist]:
        """Get watchlist by name (and optionally source)."""
        try:
            query = self.session.query(WatchlistORM).filter_by(name=name)
            if source:
                query = query.filter_by(source=source)
            orm = query.first()
            return self.to_domain(orm) if orm else None
        except Exception as e:
            logger.error(f"Error getting watchlist '{name}': {e}")
            return None

    def get_all_watchlists(self) -> List[Watchlist]:
        """Get all watchlists."""
        try:
            orms = self.session.query(WatchlistORM).order_by(WatchlistORM.name).all()
            return [self.to_domain(o) for o in orms]
        except Exception as e:
            logger.error(f"Error getting all watchlists: {e}")
            return []

    def update_symbols(self, watchlist_id: str, symbols: List[str]) -> Optional[Watchlist]:
        """Update symbols in a watchlist."""
        try:
            orm = self.session.query(WatchlistORM).filter_by(id=watchlist_id).first()
            if not orm:
                return None
            orm.symbols = symbols
            orm.last_refreshed = datetime.utcnow()
            self.session.flush()
            return self.to_domain(orm)
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating watchlist symbols: {e}")
            return None

    def upsert(self, wl: Watchlist) -> Optional[Watchlist]:
        """Create or update watchlist by name+source."""
        try:
            existing = self.session.query(WatchlistORM).filter_by(
                name=wl.name, source=wl.source
            ).first()
            if existing:
                existing.symbols = wl.symbols
                existing.description = wl.description
                existing.last_refreshed = datetime.utcnow()
                self.session.flush()
                return self.to_domain(existing)
            return self.create_from_domain(wl)
        except Exception as e:
            self.rollback()
            logger.error(f"Error upserting watchlist: {e}")
            return None

    def to_domain(self, orm: WatchlistORM) -> Watchlist:
        """Convert ORM to domain model."""
        return Watchlist(
            id=orm.id,
            name=orm.name,
            source=orm.source or 'custom',
            symbols=orm.symbols or [],
            description=orm.description or '',
            created_at=orm.created_at,
            last_refreshed=orm.last_refreshed,
        )
