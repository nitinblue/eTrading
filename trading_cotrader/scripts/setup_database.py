"""
Database Setup Script

Initializes the Trading Co-Trader database with proper schema.
Supports incremental migrations — safely adds new tables and columns
without dropping existing data.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import get_db_manager
import logging

logger = logging.getLogger(__name__)


def migrate_schema(db):
    """
    Incrementally migrate schema — add missing tables and columns.

    SQLAlchemy's create_all() handles CREATE TABLE IF NOT EXISTS,
    but does NOT add new columns to existing tables. This function
    inspects the ORM definitions vs actual DB and runs ALTER TABLE
    for any missing columns.
    """
    from sqlalchemy import inspect, text
    from core.database.schema import Base

    # Step 1: create_all() adds any entirely new tables
    db.create_all_tables()

    # Step 2: add missing columns to existing tables
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    added = []

    for table_name, table_obj in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # table was just created by create_all()

        existing_cols = {c['name'] for c in inspector.get_columns(table_name)}

        for col in table_obj.columns:
            if col.name not in existing_cols:
                # Build column type string for ALTER TABLE
                col_type = col.type.compile(dialect=db.engine.dialect)
                sql = f'ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}'
                with db.engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
                added.append(f"{table_name}.{col.name}")

    return added


def main():
    """Main setup routine"""

    print("=" * 80)
    print("Trading Co-Trader - Database Setup")
    print("=" * 80)
    print()

    # Load settings
    try:
        settings = get_settings()
        print(f"[OK] Settings loaded")
        print(f"  Database URL: {settings.database_url}")
        print(f"  Paper Trading: {settings.is_paper_trading}")
        print()
    except Exception as e:
        print(f"[FAIL] Failed to load settings: {e}")
        print("\nMake sure you have a .env file with required configuration.")
        print("See .env.example for template.")
        return 1

    # Setup logging
    setup_logging(settings)

    # Get database manager
    db = get_db_manager()

    # Check if database exists
    existing = False
    try:
        existing = db.health_check()
        if existing:
            print("⚠️  Database already exists!")
            response = input("Do you want to:\n  1) Keep existing data (+ apply migrations)\n  2) Reset database (DESTROYS ALL DATA)\nChoice [1]: ").strip()

            if response == "2":
                print("\n⚠️  WARNING: This will DELETE ALL DATA!")
                confirm = input("Type 'DELETE' to confirm: ").strip()
                if confirm == "DELETE":
                    print("\nDropping all tables...")
                    db.drop_all_tables()
                    print("[OK] Tables dropped")
                    existing = False
                else:
                    print("Aborted.")
                    return 0
    except:
        pass

    # Create or migrate tables
    if existing:
        print("\nMigrating schema (adding new tables/columns)...")
        try:
            added = migrate_schema(db)
            if added:
                print(f"[OK] Added {len(added)} new column(s):")
                for col in added:
                    print(f"    + {col}")
            else:
                print("[OK] Schema is up to date — no migrations needed")
        except Exception as e:
            print(f"[FAIL] Migration failed: {e}")
            logger.exception("Full error:")
            return 1
    else:
        print("\nCreating database tables...")
        try:
            db.create_all_tables()
            print("[OK] All tables created successfully")
        except Exception as e:
            print(f"[FAIL] Failed to create tables: {e}")
            logger.exception("Full error:")
            return 1

    # Verify tables
    print("\nVerifying database schema...")
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = sorted(inspector.get_table_names())

        print(f"\nTables ({len(tables)}):")
        for table in tables:
            cols = inspector.get_columns(table)
            print(f"  [OK] {table} ({len(cols)} columns)")

        print(f"\n[OK] Database setup complete!")
        print(f"\nDatabase location: {settings.database_url}")

    except Exception as e:
        print(f"[FAIL] Verification failed: {e}")
        logger.exception("Full error:")
        return 1

    # Summary
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Run sync to import your portfolio:")
    print("   python -m trading_cotrader.cli.init_portfolios")
    print("\n2. Run workflow engine:")
    print("   python -m trading_cotrader.runners.run_workflow --once --no-broker --mock")
    print("\n3. Run tests:")
    print("   pytest trading_cotrader/tests/ -v")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())