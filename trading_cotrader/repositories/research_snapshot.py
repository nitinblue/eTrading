"""
Research Snapshot Repository — Upsert/load for DB-backed ResearchContainer.

Persists ResearchEntry and MacroContext to research_snapshots / macro_snapshots
tables. Enables instant cold start without calling market_regime library.
"""

from datetime import date
from typing import Dict, List, Optional
import uuid
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from trading_cotrader.core.database.schema import (
    ResearchSnapshotORM,
    MacroSnapshotORM,
)

logger = logging.getLogger(__name__)


class ResearchSnapshotRepository:
    """Repository for research snapshot persistence."""

    def __init__(self, session: Session):
        self.session = session

    # -----------------------------------------------------------------
    # Research snapshots
    # -----------------------------------------------------------------

    def upsert_research(self, symbol: str, snapshot_date: date, data: dict) -> None:
        """Upsert a single research snapshot row."""
        existing = (
            self.session.query(ResearchSnapshotORM)
            .filter_by(symbol=symbol, snapshot_date=snapshot_date)
            .first()
        )

        if existing:
            for key, value in data.items():
                if hasattr(existing, key) and key not in ('id', 'symbol', 'snapshot_date', 'created_at'):
                    setattr(existing, key, value)
        else:
            orm = ResearchSnapshotORM(
                id=str(uuid.uuid4()),
                symbol=symbol,
                snapshot_date=snapshot_date,
                **{k: v for k, v in data.items()
                   if hasattr(ResearchSnapshotORM, k)
                   and k not in ('id', 'symbol', 'snapshot_date', 'created_at', 'updated_at')},
            )
            try:
                nested = self.session.begin_nested()
                self.session.add(orm)
                nested.commit()
            except IntegrityError:
                nested.rollback()
                # Race condition — update instead
                existing = (
                    self.session.query(ResearchSnapshotORM)
                    .filter_by(symbol=symbol, snapshot_date=snapshot_date)
                    .first()
                )
                if existing:
                    for key, value in data.items():
                        if hasattr(existing, key) and key not in ('id', 'symbol', 'snapshot_date', 'created_at'):
                            setattr(existing, key, value)

    def bulk_upsert_research(self, entries: List[dict], snapshot_date: date) -> int:
        """Upsert multiple research entries. Returns count upserted."""
        count = 0
        for entry_data in entries:
            symbol = entry_data.get('symbol')
            if not symbol:
                continue
            try:
                self.upsert_research(symbol, snapshot_date, entry_data)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert research for {symbol}: {e}")
        return count

    def load_latest_research(self) -> List[ResearchSnapshotORM]:
        """Load all research snapshots from the most recent date."""
        # Find the latest snapshot_date
        latest_date = (
            self.session.query(ResearchSnapshotORM.snapshot_date)
            .order_by(ResearchSnapshotORM.snapshot_date.desc())
            .limit(1)
            .scalar()
        )
        if not latest_date:
            return []

        return (
            self.session.query(ResearchSnapshotORM)
            .filter(ResearchSnapshotORM.snapshot_date == latest_date)
            .all()
        )

    # -----------------------------------------------------------------
    # Macro snapshots
    # -----------------------------------------------------------------

    def upsert_macro(self, snapshot_date: date, data: dict) -> None:
        """Upsert a macro snapshot row."""
        existing = (
            self.session.query(MacroSnapshotORM)
            .filter_by(snapshot_date=snapshot_date)
            .first()
        )

        if existing:
            for key, value in data.items():
                if hasattr(existing, key) and key not in ('id', 'snapshot_date', 'created_at'):
                    setattr(existing, key, value)
        else:
            orm = MacroSnapshotORM(
                id=str(uuid.uuid4()),
                snapshot_date=snapshot_date,
                **{k: v for k, v in data.items()
                   if hasattr(MacroSnapshotORM, k)
                   and k not in ('id', 'snapshot_date', 'created_at', 'updated_at')},
            )
            try:
                nested = self.session.begin_nested()
                self.session.add(orm)
                nested.commit()
            except IntegrityError:
                nested.rollback()
                existing = (
                    self.session.query(MacroSnapshotORM)
                    .filter_by(snapshot_date=snapshot_date)
                    .first()
                )
                if existing:
                    for key, value in data.items():
                        if hasattr(existing, key) and key not in ('id', 'snapshot_date', 'created_at'):
                            setattr(existing, key, value)

    def load_latest_macro(self) -> Optional[MacroSnapshotORM]:
        """Load the most recent macro snapshot."""
        return (
            self.session.query(MacroSnapshotORM)
            .order_by(MacroSnapshotORM.snapshot_date.desc())
            .first()
        )
