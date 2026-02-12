"""
Test fixtures for fetcher tests.

Provides database fixtures and utilities for testing FetcherManager.
Requires docker-compose postgres service to be running.
"""

import os

import pytest
import pytest_asyncio

from src.core.storage.base import DatabaseConfig
from src.core.storage.postgres import Base, Database

# Use test database to avoid polluting production data
TEST_DB = "assistant_test"


@pytest.fixture(scope="module")
def database_config() -> DatabaseConfig:
    """Database configuration for tests."""
    return DatabaseConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_TEST_DB", TEST_DB),
        user=os.getenv("POSTGRES_USER", "assistant"),
        password=os.getenv("POSTGRES_PASSWORD", "assistant"),
        pool_size=2,
        pool_max_overflow=2,
        echo=False,
    )


@pytest_asyncio.fixture
async def database(database_config: DatabaseConfig) -> Database:
    """
    Provide a connected database instance with tables created.

    Creates tables at setup and drops them at teardown.
    Function-scoped to avoid connection sharing issues.
    """
    db = Database(database_config)
    await db.connect()

    # Create all tables
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield db

    # Drop all tables
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await db.disconnect()


@pytest_asyncio.fixture
async def clean_database(database: Database) -> Database:
    """
    Provide a clean database for each test.

    Cleans up all data between tests.
    """
    # Clean up data before test
    from src.core.models import Article, Category, Digest, JobRun, Setting, Source

    async with database.session() as session:
        # Delete in correct order to respect foreign keys
        await session.execute(Article.__table__.delete())
        await session.execute(Digest.__table__.delete())
        await session.execute(Source.__table__.delete())
        await session.execute(Category.__table__.delete())
        await session.execute(Setting.__table__.delete())
        await session.execute(JobRun.__table__.delete())
        await session.commit()

    yield database

    # Clean up data after test
    async with database.session() as session:
        await session.execute(Article.__table__.delete())
        await session.execute(Digest.__table__.delete())
        await session.execute(Source.__table__.delete())
        await session.execute(Category.__table__.delete())
        await session.execute(Setting.__table__.delete())
        await session.execute(JobRun.__table__.delete())
        await session.commit()
