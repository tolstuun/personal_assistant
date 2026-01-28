"""
PostgreSQL database implementation.

Uses SQLAlchemy with async support for database operations.
Provides connection pooling and session management.
"""

import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config.loader import get_config
from src.core.storage.base import BaseDatabase, DatabaseConfig
from src.core.storage.exceptions import ConfigurationError, ConnectionError

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Database(BaseDatabase):
    """
    PostgreSQL database implementation using SQLAlchemy async.

    Usage:
        db = Database(config)
        await db.connect()

        async with db.session() as session:
            result = await session.execute(text("SELECT 1"))
            row = result.scalar()

        await db.disconnect()
    """

    def __init__(self, config: DatabaseConfig):
        """Initialize database with configuration."""
        super().__init__(config)
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def _build_url(self) -> str:
        """Build database connection URL."""
        return (
            f"postgresql+asyncpg://{self.config.user}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{self.config.database}"
        )

    async def connect(self) -> None:
        """Establish connection pool to the database."""
        if self._engine is not None:
            return

        try:
            url = self._build_url()
            self._engine = create_async_engine(
                url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.pool_max_overflow,
                echo=self.config.echo,
            )
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info(
                f"Connected to PostgreSQL at {self.config.host}:{self.config.port}"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}") from e

    async def disconnect(self) -> None:
        """Close all database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Disconnected from PostgreSQL")

    async def health_check(self) -> bool:
        """Check if database is reachable by executing a simple query."""
        if self._engine is None:
            return False

        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(f"PostgreSQL health check failed: {e}")
            return False

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provide a transactional session scope.

        Usage:
            async with db.session() as session:
                result = await session.execute(query)
                await session.commit()
        """
        if self._session_factory is None:
            raise ConnectionError("Database not connected. Call connect() first.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tables(self) -> None:
        """Create all tables defined in models."""
        if self._engine is None:
            raise ConnectionError("Database not connected. Call connect() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")

    async def drop_tables(self) -> None:
        """Drop all tables. Use with caution."""
        if self._engine is None:
            raise ConnectionError("Database not connected. Call connect() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped")


def _load_config() -> DatabaseConfig:
    """Load database configuration from config files."""
    config = get_config()
    postgres_config = config.get("postgres", {})

    if not postgres_config:
        raise ConfigurationError("PostgreSQL configuration not found")

    return DatabaseConfig(
        host=postgres_config.get("host", "localhost"),
        port=int(postgres_config.get("port", 5432)),
        database=postgres_config.get("database", "assistant"),
        user=postgres_config.get("user", "assistant"),
        password=postgres_config.get("password", "assistant"),
        pool_size=int(postgres_config.get("pool_size", 5)),
        pool_max_overflow=int(postgres_config.get("pool_max_overflow", 10)),
        echo=postgres_config.get("echo", False),
    )


# Global database instance
_db_instance: Database | None = None


async def get_db() -> Database:
    """
    Get the global database instance.

    Creates and connects the instance on first call.
    Subsequent calls return the same instance.

    Returns:
        Connected Database instance.
    """
    global _db_instance

    if _db_instance is None:
        config = _load_config()
        _db_instance = Database(config)
        await _db_instance.connect()

    return _db_instance


async def close_db() -> None:
    """Close the global database instance."""
    global _db_instance

    if _db_instance is not None:
        await _db_instance.disconnect()
        _db_instance = None
