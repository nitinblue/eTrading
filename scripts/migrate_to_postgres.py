"""
SQLite → PostgreSQL Migration Script

Usage:
    # 1. Start PostgreSQL (via docker-compose or local install)
    # 2. Set DATABASE_URL in .env:
    #    DATABASE_URL=postgresql://cotrader:password@localhost:5432/cotrader
    # 3. Run this script:
    python scripts/migrate_to_postgres.py

    Options:
      --schema-only    Create tables without migrating data
      --data-only      Migrate data (tables must exist)
      --drop-first     Drop all PostgreSQL tables before creating

What it does:
    1. Reads current SQLite database (trading_cotrader.db)
    2. Creates all tables in PostgreSQL from ORM models
    3. Copies all data row by row
    4. Validates row counts match
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

SQLITE_URL = "sqlite:///trading_cotrader.db"


def get_postgres_url():
    """Get PostgreSQL URL from env."""
    from trading_cotrader.config.settings import get_settings
    settings = get_settings()
    url = settings.database_url
    if 'postgresql' not in url:
        url = os.environ.get('DATABASE_URL', '')
    if 'postgresql' not in url:
        raise ValueError(
            "No PostgreSQL URL found. Set DATABASE_URL in .env:\n"
            "  DATABASE_URL=postgresql://cotrader:password@localhost:5432/cotrader"
        )
    return url


def create_schema(pg_url: str, drop_first: bool = False):
    """Create all tables in PostgreSQL from ORM models."""
    from sqlalchemy import create_engine
    from trading_cotrader.core.database.schema import Base

    engine = create_engine(pg_url, pool_pre_ping=True)

    if drop_first:
        logger.info("Dropping all PostgreSQL tables...")
        Base.metadata.drop_all(bind=engine)

    logger.info("Creating PostgreSQL tables from ORM models...")
    Base.metadata.create_all(bind=engine)

    # Verify
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Created {len(tables)} tables: {', '.join(sorted(tables))}")

    engine.dispose()
    return tables


def migrate_data(pg_url: str):
    """Copy all data from SQLite to PostgreSQL."""
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.orm import sessionmaker

    sqlite_engine = create_engine(SQLITE_URL)
    pg_engine = create_engine(pg_url, pool_pre_ping=True)

    sqlite_session = sessionmaker(bind=sqlite_engine)()
    pg_session = sessionmaker(bind=pg_engine)()

    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()

    logger.info(f"\nMigrating data from {len(tables)} SQLite tables...")

    total_rows = 0
    for table_name in sorted(tables):
        try:
            # Read from SQLite
            rows = sqlite_session.execute(text(f"SELECT * FROM {table_name}")).fetchall()
            if not rows:
                logger.info(f"  {table_name}: 0 rows (empty)")
                continue

            # Get column names
            columns = [col['name'] for col in inspector.get_columns(table_name)]

            # Check if table exists in PG
            pg_inspector = inspect(pg_engine)
            if table_name not in pg_inspector.get_table_names():
                logger.warning(f"  {table_name}: SKIPPED (not in PostgreSQL schema)")
                continue

            pg_columns = [col['name'] for col in pg_inspector.get_columns(table_name)]

            # Only use columns that exist in both
            common_cols = [c for c in columns if c in pg_columns]

            # Clear existing PG data for this table
            pg_session.execute(text(f"DELETE FROM {table_name}"))

            # Insert rows
            col_list = ', '.join(common_cols)
            placeholders = ', '.join(f':{c}' for c in common_cols)
            insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

            batch = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    if col in common_cols:
                        row_dict[col] = row[i]
                batch.append(row_dict)

            if batch:
                pg_session.execute(text(insert_sql), batch)

            total_rows += len(rows)
            logger.info(f"  {table_name}: {len(rows)} rows migrated ({len(common_cols)} columns)")

        except Exception as e:
            logger.error(f"  {table_name}: FAILED — {e}")
            pg_session.rollback()
            continue

    pg_session.commit()
    sqlite_session.close()
    pg_session.close()

    logger.info(f"\nTotal: {total_rows} rows migrated")

    sqlite_engine.dispose()
    pg_engine.dispose()


def validate(pg_url: str):
    """Validate row counts match between SQLite and PostgreSQL."""
    from sqlalchemy import create_engine, text, inspect

    sqlite_engine = create_engine(SQLITE_URL)
    pg_engine = create_engine(pg_url)

    sqlite_inspector = inspect(sqlite_engine)
    pg_inspector = inspect(pg_engine)

    sqlite_tables = set(sqlite_inspector.get_table_names())
    pg_tables = set(pg_inspector.get_table_names())

    logger.info("\nValidation:")
    mismatches = 0

    for table in sorted(sqlite_tables & pg_tables):
        try:
            with sqlite_engine.connect() as conn:
                sqlite_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            with pg_engine.connect() as conn:
                pg_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

            status = "OK" if sqlite_count == pg_count else "MISMATCH"
            if status == "MISMATCH":
                mismatches += 1
            symbol = "✓" if status == "OK" else "✗"
            logger.info(f"  {symbol} {table}: SQLite={sqlite_count} PostgreSQL={pg_count} [{status}]")
        except Exception as e:
            logger.error(f"  ✗ {table}: {e}")
            mismatches += 1

    only_sqlite = sqlite_tables - pg_tables
    if only_sqlite:
        logger.info(f"\n  Tables only in SQLite: {only_sqlite}")

    only_pg = pg_tables - sqlite_tables
    if only_pg:
        logger.info(f"\n  Tables only in PostgreSQL: {only_pg}")

    sqlite_engine.dispose()
    pg_engine.dispose()

    if mismatches == 0:
        logger.info("\n✓ All tables match. Migration successful.")
    else:
        logger.warning(f"\n✗ {mismatches} mismatches found.")

    return mismatches == 0


def main():
    parser = argparse.ArgumentParser(description='Migrate SQLite to PostgreSQL')
    parser.add_argument('--schema-only', action='store_true', help='Create tables only')
    parser.add_argument('--data-only', action='store_true', help='Migrate data only')
    parser.add_argument('--drop-first', action='store_true', help='Drop PG tables before creating')
    parser.add_argument('--validate-only', action='store_true', help='Just validate counts')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SQLite → PostgreSQL Migration")
    logger.info("=" * 60)

    # Check SQLite exists
    if not os.path.exists('trading_cotrader.db'):
        logger.error("SQLite database not found: trading_cotrader.db")
        logger.error("Run from the eTrading project root directory.")
        return 1

    try:
        pg_url = get_postgres_url()
    except ValueError as e:
        logger.error(str(e))
        return 1

    logger.info(f"Source: {SQLITE_URL}")
    logger.info(f"Target: {pg_url.split('@')[1] if '@' in pg_url else pg_url}")

    if args.validate_only:
        validate(pg_url)
        return 0

    if not args.data_only:
        create_schema(pg_url, drop_first=args.drop_first)

    if not args.schema_only:
        migrate_data(pg_url)
        validate(pg_url)

    logger.info("\nDone. Update .env to use PostgreSQL:")
    logger.info(f"  DATABASE_URL={pg_url}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
