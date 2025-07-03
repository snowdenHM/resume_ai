"""
Database configuration and session management.
Provides async database connections using SQLAlchemy 2.0 and asyncpg.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import MetaData, event, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

# Configure Logging
logger = logging.getLogger(__name__)

# Database metadata
meta_data = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)

class Base(DeclarativeBase):
    """ Base class for all database models """
    meta_data = meta_data

# Global engine and session maker
engine: Optional[AsyncEngine] = None
async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None

def create_engine() -> AsyncEngine:
    """Create async database engine with optimized settings."""
    
    # Engine configuration for production
    engine_kwargs = {
        "echo": settings.DEBUG,
        "echo_pool": settings.DEBUG,
        "pool_pre_ping": True,
        "pool_recycle": 300,  # 5 minutes
        "pool_size": 20,
        "max_overflow": 0,
        "connect_args": {
            "server_settings": {
                "jit": "off",  # Disable JIT for better connection startup
                "application_name": settings.APP_NAME,
            },
            "command_timeout": 60,
            "prepared_statement_cache_size": 0,  # Disable prepared statement cache
        }
    }
    
    # Use NullPool for testing to avoid connection issues
    if settings.DEBUG or "test" in str(settings.DATABASE_URL):
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs.pop("pool_size", None)
        engine_kwargs.pop("max_overflow", None)
        engine_kwargs.pop("pool_pre_ping", None)
        engine_kwargs.pop("pool_recycle", None)
    
    return create_async_engine(str(settings.DATABASE_URL), **engine_kwargs)

@event.listens_for(pool.Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance (if using SQLite for testing)."""
    if "sqlite" in str(settings.DATABASE_URL):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=1000")
            cursor.execute("PRAGMA temp_store=MEMORY")


async def init_db() -> None:
    """Initialize database connection and session maker."""
    global engine, async_session_maker
    
    try:
        engine = create_engine()
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False
        )
        
        # Test connection
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: None)
        
        logger.info("Database connection initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """Close database connections."""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database session.
    
    Yields:
        AsyncSession: Database session
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


class DatabaseManager:
    """Database manager for handling connections and transactions."""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_maker: Optional[async_sessionmaker[AsyncSession]] = None
    
    async def init(self) -> None:
        """Initialize database manager."""
        self.engine = create_engine()
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Test connection
        async with self.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: None)
        
        logger.info("Database manager initialized")
    
    async def close(self) -> None:
        """Close database manager."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database manager closed")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session context manager."""
        if not self.session_maker:
            raise RuntimeError("Database manager not initialized")
        
        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database transaction error: {e}")
                raise
            finally:
                await session.close()
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            raise RuntimeError("Database manager not initialized")
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created")
    
    async def drop_tables(self) -> None:
        """Drop all database tables."""
        if not self.engine:
            raise RuntimeError("Database manager not initialized")
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.info("Database tables dropped")


# Global database manager instance
db_manager = DatabaseManager()


# Health check function
async def check_database_health() -> bool:
    """
    Check database connectivity.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        if not engine:
            return False
        
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute("SELECT 1"))
        
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# Utility functions
async def execute_query(query: str, params: Optional[dict] = None) -> any:
    """
    Execute raw SQL query.
    
    Args:
        query: SQL query string
        params: Query parameters
    
    Returns:
        Query result
    """
    async with get_session_context() as session:
        result = await session.execute(query, params or {})
        return result


async def get_table_info(table_name: str) -> dict:
    """
    Get table information.
    
    Args:
        table_name: Name of the table
    
    Returns:
        dict: Table information
    """
    query = """
    SELECT 
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns 
    WHERE table_name = :table_name
    ORDER BY ordinal_position
    """
    
    async with get_session_context() as session:
        result = await session.execute(query, {"table_name": table_name})
        columns = result.fetchall()
        
        return {
            "table_name": table_name,
            "columns": [
                {
                    "name": col.column_name,
                    "type": col.data_type,
                    "nullable": col.is_nullable == "YES",
                    "default": col.column_default
                }
                for col in columns
            ]
        }


# Export for easy imports
__all__ = [
    "Base",
    "engine",
    "async_session_maker",
    "init_db",
    "close_db",
    "get_session",
    "get_session_context",
    "DatabaseManager",
    "db_manager",
    "check_database_health",
    "execute_query",
    "get_table_info"
]