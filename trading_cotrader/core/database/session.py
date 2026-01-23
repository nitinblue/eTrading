"""
Database Session Management

Provides:
- Database engine creation
- Session factory
- Context managers for transactions
- Database initialization
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import text
import logging

from trading_cotrader.config.settings import get_settings
from trading_cotrader.core.database.schema import Base

logger = logging.getLogger(__name__)


# ============================================================================
# Engine & Session Factory
# ============================================================================

class DatabaseManager:
    """Manages database connections and sessions"""
    
    def __init__(self, database_url: str = None):
        """
        Initialize database manager
        
        Args:
            database_url: Database URL (defaults to settings)
        """
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.engine = None
        self.SessionLocal = None
        
        self._create_engine()
    
    def _create_engine(self):
        """Create SQLAlchemy engine"""
        settings = get_settings()
        engine_kwargs = settings.get_database_engine_kwargs()
        
        # SQLite specific configuration
        if 'sqlite' in self.database_url:
            # Enable foreign keys for SQLite
            engine_kwargs['poolclass'] = StaticPool
            
            self.engine = create_engine(self.database_url, **engine_kwargs)
            
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            self.engine = create_engine(self.database_url, **engine_kwargs)
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info(f"Database engine created: {self.database_url}")
    
    def create_all_tables(self):
        """Create all tables"""
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("✓ All tables created")
    
    def drop_all_tables(self):
        """Drop all tables (DANGEROUS - use only in testing!)"""
        logger.warning("Dropping all database tables...")
        
        # For SQLite, need to handle indexes separately
        if 'sqlite' in self.database_url:
            # Drop all tables individually to avoid index issues
            from sqlalchemy import inspect, MetaData
            
            inspector = inspect(self.engine)
            metadata = MetaData()
            metadata.reflect(bind=self.engine)
            
            # Drop all tables
            metadata.drop_all(bind=self.engine)
            
            logger.warning("All tables dropped successfully")
        else:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All tables dropped successfully")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations
        
        Usage:
            with db.session_scope() as session:
                session.add(some_object)
                # Automatically commits on success, rolls back on error
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session rollback due to error: {e}")
            raise
        finally:
            session.close()
    
    def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# ============================================================================
# Global Database Instance
# ============================================================================

_db_manager: DatabaseManager = None


def get_db_manager() -> DatabaseManager:
    """
    Get global database manager instance (singleton)
    
    Usage:
        from core.database.session import get_db_manager
        
        db = get_db_manager()
        with db.session_scope() as session:
            # Use session
            pass
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_session() -> Session:
    """
    Get a new database session (convenience function)
    
    Usage:
        from core.database.session import get_session
        
        session = get_session()
        try:
            # Use session
            session.commit()
        finally:
            session.close()
    """
    return get_db_manager().get_session()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager for database sessions (convenience function)
    
    Usage:
        from core.database.session import session_scope
        
        with session_scope() as session:
            session.add(some_object)
    """
    db = get_db_manager()
    with db.session_scope() as session:
        yield session


def init_database():
    """
    Initialize database (create tables if they don't exist)
    
    Usage:
        from core.database.session import init_database
        init_database()
    """
    db = get_db_manager()
    db.create_all_tables()


def reset_database():
    """
    Reset database (drop and recreate all tables)
    DANGEROUS - only use in development/testing!
    
    Usage:
        from core.database.session import reset_database
        reset_database()
    """
    db = get_db_manager()
    db.drop_all_tables()
    db.create_all_tables()


# ============================================================================
# Database Migrations Support (for Alembic)
# ============================================================================

def get_engine():
    """Get database engine (for Alembic migrations)"""
    return get_db_manager().engine


# ============================================================================
# Testing Support
# ============================================================================

def create_test_database() -> DatabaseManager:
    """
    Create in-memory SQLite database for testing
    
    Usage:
        def test_something():
            db = create_test_database()
            with db.session_scope() as session:
                # Test code
                pass
    """
    db = DatabaseManager(database_url="sqlite:///:memory:")
    db.create_all_tables()
    return db


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    from config.settings import setup_logging, get_settings
    
    # Setup logging
    setup_logging()
    
    # Initialize database
    logger.info("Initializing database...")
    init_database()
    
    # Health check
    db = get_db_manager()
    if db.health_check():
        logger.info("✓ Database is healthy")
    else:
        logger.error("✗ Database health check failed")
    
    # Example: Using session scope
    with session_scope() as session:
        # Example query
        from core.database.schema import PortfolioORM
        
        count = session.query(PortfolioORM).count()
        logger.info(f"Portfolios in database: {count}")
    
    logger.info("Database session example completed")