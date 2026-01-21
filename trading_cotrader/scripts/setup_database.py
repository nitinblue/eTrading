"""
Database Setup Script

Initializes the Trading Co-Trader database with proper schema
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


def main():
    """Main setup routine"""
    
    print("=" * 80)
    print("Trading Co-Trader - Database Setup")
    print("=" * 80)
    print()
    
    # Load settings
    try:
        settings = get_settings()
        print(f"✓ Settings loaded")
        print(f"  Database URL: {settings.database_url}")
        print(f"  Paper Trading: {settings.is_paper_trading}")
        print()
    except Exception as e:
        print(f"✗ Failed to load settings: {e}")
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
            response = input("Do you want to:\n  1) Keep existing data\n  2) Reset database (DESTROYS ALL DATA)\nChoice [1]: ").strip()
            
            if response == "2":
                print("\n⚠️  WARNING: This will DELETE ALL DATA!")
                confirm = input("Type 'DELETE' to confirm: ").strip()
                if confirm == "DELETE":
                    print("\nDropping all tables...")
                    db.drop_all_tables()
                    print("✓ Tables dropped")
                    existing = False
                else:
                    print("Aborted.")
                    return 0
    except:
        pass
    
    # Create tables
    if not existing:
        print("\nCreating database tables...")
        try:
            db.create_all_tables()
            print("✓ All tables created successfully")
        except Exception as e:
            print(f"✗ Failed to create tables: {e}")
            logger.exception("Full error:")
            return 1
    
    # Verify tables
    print("\nVerifying database schema...")
    try:
        from core.database.schema import (
            SymbolORM, PortfolioORM, PositionORM, TradeORM, LegORM,
            StrategyORM, OrderORM, TradeEventORM, RecognizedPatternORM,
            DailyPerformanceORM, GreeksHistoryORM
        )
        
        tables = [
            SymbolORM.__tablename__,
            PortfolioORM.__tablename__,
            PositionORM.__tablename__,
            TradeORM.__tablename__,
            LegORM.__tablename__,
            StrategyORM.__tablename__,
            OrderORM.__tablename__,
            TradeEventORM.__tablename__,
            RecognizedPatternORM.__tablename__,
            DailyPerformanceORM.__tablename__,
            GreeksHistoryORM.__tablename__,
        ]
        
        print("\nTables created:")
        for table in tables:
            print(f"  ✓ {table}")
        
        print(f"\n✓ Database setup complete!")
        print(f"\nDatabase location: {settings.database_url}")
        
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        logger.exception("Full error:")
        return 1
    
    # Summary
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Run sync to import your portfolio:")
    print("   python -m cli sync")
    print("\n2. View your portfolio:")
    print("   python -m cli analyze")
    print("\n3. Validate data integrity:")
    print("   python -m cli validate")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())