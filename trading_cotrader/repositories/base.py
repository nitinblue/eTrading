"""
Base Repository Pattern

Provides common CRUD operations for all repositories.
Each specific repository inherits from this base.
"""

from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

# Type variables for generic repository
ModelType = TypeVar('ModelType')
ORMType = TypeVar('ORMType')


class BaseRepository(Generic[ModelType, ORMType]):
    """
    Base repository with common CRUD operations
    
    Usage:
        class PositionRepository(BaseRepository[dm.Position, PositionORM]):
            def __init__(self, session: Session):
                super().__init__(session, PositionORM)
    """
    
    def __init__(self, session: Session, model_class: Type[ORMType]):
        """
        Initialize repository
        
        Args:
            session: SQLAlchemy session
            model_class: ORM model class
        """
        self.session = session
        self.model_class = model_class
    
    def get_by_id(self, id: str) -> Optional[ORMType]:
        """
        Get entity by ID
        
        Args:
            id: Entity ID
            
        Returns:
            ORM instance or None
        """
        try:
            return self.session.query(self.model_class).filter_by(id=id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model_class.__name__} by id {id}: {e}")
            return None
    
    def get_all(self) -> List[ORMType]:
        """Get all entities"""
        try:
            return self.session.query(self.model_class).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model_class.__name__}: {e}")
            return []
    
    def create(self, orm_instance: ORMType) -> Optional[ORMType]:
        """
        Create new entity
        
        Args:
            orm_instance: ORM instance to create
            
        Returns:
            Created ORM instance or None on error
        """
        try:
            self.session.add(orm_instance)
            self.session.flush()  # Get ID without committing
            return orm_instance
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error creating {self.model_class.__name__}: {e}")
            return None
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            return None
    
    def update(self, orm_instance: ORMType) -> Optional[ORMType]:
        """
        Update entity
        
        Args:
            orm_instance: ORM instance to update
            
        Returns:
            Updated ORM instance or None on error
        """
        try:
            self.session.merge(orm_instance)
            self.session.flush()
            return orm_instance
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating {self.model_class.__name__}: {e}")
            return None
    
    def delete(self, id: str) -> bool:
        """
        Delete entity by ID
        
        Args:
            id: Entity ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            instance = self.get_by_id(id)
            if instance:
                self.session.delete(instance)
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deleting {self.model_class.__name__} {id}: {e}")
            return False
    
    def delete_all(self) -> int:
        """
        Delete all entities (use with caution!)
        
        Returns:
            Number of deleted entities
        """
        try:
            count = self.session.query(self.model_class).count()
            self.session.query(self.model_class).delete()
            self.session.flush()
            logger.warning(f"Deleted {count} {self.model_class.__name__} instances")
            return count
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deleting all {self.model_class.__name__}: {e}")
            return 0
    
    def count(self) -> int:
        """Count total entities"""
        try:
            return self.session.query(self.model_class).count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model_class.__name__}: {e}")
            return 0
    
    def exists(self, id: str) -> bool:
        """Check if entity exists"""
        try:
            return self.session.query(self.model_class).filter_by(id=id).first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model_class.__name__} {id}: {e}")
            return False
    
    def commit(self):
        """Commit transaction"""
        try:
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error committing transaction: {e}")
            raise
    
    def rollback(self):
        """Rollback transaction"""
        self.session.rollback()
    
    def flush(self):
        """Flush changes to database (without committing)"""
        try:
            self.session.flush()
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error flushing session: {e}")
            raise


class RepositoryError(Exception):
    """Custom exception for repository operations"""
    pass


class DuplicateEntityError(RepositoryError):
    """Raised when trying to create a duplicate entity"""
    pass


class EntityNotFoundError(RepositoryError):
    """Raised when entity not found"""
    pass