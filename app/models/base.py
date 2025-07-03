"""
Base model classes with common fields and utilities.
"""

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import Column, DateTime, Boolean, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

from app.database import Base


class TimestampMixin:
    """Mixin for adding timestamp fields to models."""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Record creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        comment="Record last update timestamp"
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Soft delete flag"
    )
    
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Soft delete timestamp"
    )


class UUIDMixin:
    """Mixin for UUID primary key."""
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        comment="Unique identifier"
    )


class BaseModel(Base, TimestampMixin, UUIDMixin):
    """Base model class with common fields and methods."""
    
    __abstract__ = True
    
    def to_dict(self, exclude: Optional[set] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            exclude: Set of field names to exclude
            
        Returns:
            Dictionary representation of the model
        """
        exclude = exclude or set()
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                
                # Handle datetime objects
                if isinstance(value, datetime):
                    value = value.isoformat()
                # Handle UUID objects
                elif hasattr(value, 'hex'):
                    value = str(value)
                
                result[column.name] = value
        
        return result
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Update model instance from dictionary.
        
        Args:
            data: Dictionary with field values
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ('id', 'created_at'):
                setattr(self, key, value)
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get table name for the model."""
        return cls.__tablename__
    
    @classmethod
    def get_column_names(cls) -> list:
        """Get list of column names."""
        return [column.name for column in cls.__table__.columns]
    
    def __repr__(self) -> str:
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"


class SoftDeleteModel(BaseModel, SoftDeleteMixin):
    """Base model with soft delete functionality."""
    
    __abstract__ = True
    
    def soft_delete(self) -> None:
        """Mark record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
    
    def restore(self) -> None:
        """Restore soft deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class AuditMixin:
    """Mixin for audit fields."""
    
    created_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who created the record"
    )
    
    updated_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who last updated the record"
    )


class VersionMixin:
    """Mixin for record versioning."""
    
    version = Column(
        String(50),
        nullable=False,
        default="1.0",
        comment="Record version"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Active version flag"
    )


class MetadataMixin:
    """Mixin for storing additional metadata."""
    
    @declared_attr
    def metadata_(cls):
        return Column(
            "metadata",
            String,
            nullable=True,
            comment="Additional metadata as JSON string"
        )


class AuditableModel(BaseModel, AuditMixin):
    """Base model with audit fields."""
    
    __abstract__ = True


class VersionedModel(BaseModel, VersionMixin):
    """Base model with versioning support."""
    
    __abstract__ = True


class FullAuditModel(BaseModel, AuditMixin, SoftDeleteMixin):
    """Base model with full audit trail and soft delete."""
    
    __abstract__ = True


# Common query mixins
class QueryMixin:
    """Mixin for common query methods."""
    
    @classmethod
    async def get_by_id(cls, session, record_id: uuid.UUID):
        """Get record by ID."""
        from sqlalchemy import select
        
        query = select(cls).where(cls.id == record_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_all(cls, session, limit: int = 100, offset: int = 0):
        """Get all records with pagination."""
        from sqlalchemy import select
        
        query = select(cls).limit(limit).offset(offset)
        result = await session.execute(query)
        return result.scalars().all()
    
    @classmethod
    async def create(cls, session, **kwargs):
        """Create new record."""
        instance = cls(**kwargs)
        session.add(instance)
        await session.flush()
        return instance
    
    async def update(self, session, **kwargs):
        """Update record."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        await session.flush()
        return self
    
    async def delete(self, session):
        """Delete record."""
        await session.delete(self)
        await session.flush()


# Add QueryMixin to base models
BaseModel.__bases__ = BaseModel.__bases__ + (QueryMixin,)
SoftDeleteModel.__bases__ = SoftDeleteModel.__bases__ + (QueryMixin,)


# Helper functions
def create_enum_field(enum_class, field_name: str = "status", **kwargs):
    """Create an enum field with proper PostgreSQL enum type."""
    from sqlalchemy import Enum
    
    return Column(
        Enum(enum_class, name=f"{field_name}_enum"),
        nullable=kwargs.get('nullable', False),
        default=kwargs.get('default'),
        index=kwargs.get('index', True),
        comment=kwargs.get('comment', f"{field_name.title()} field")
    )


def create_json_field(field_name: str = "data", **kwargs):
    """Create a JSON field for PostgreSQL."""
    from sqlalchemy.dialects.postgresql import JSONB
    
    return Column(
        field_name,
        JSONB,
        nullable=kwargs.get('nullable', True),
        default=kwargs.get('default', dict),
        comment=kwargs.get('comment', f"{field_name.title()} JSON field")
    )


def create_text_search_field(field_name: str = "search_vector"):
    """Create a text search vector field for PostgreSQL full-text search."""
    from sqlalchemy.dialects.postgresql import TSVECTOR
    
    return Column(
        field_name,
        TSVECTOR,
        nullable=True,
        index=True,
        comment="Full-text search vector"
    )


# Export for easy imports
__all__ = [
    "BaseModel",
    "SoftDeleteModel",
    "AuditableModel",
    "VersionedModel",
    "FullAuditModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDMixin",
    "AuditMixin",
    "VersionMixin",
    "MetadataMixin",
    "QueryMixin",
    "create_enum_field",
    "create_json_field",
    "create_text_search_field"
]