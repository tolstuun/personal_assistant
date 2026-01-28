"""
Test fixtures for storage tests.

Provides configured instances of all storage backends.
Requires docker-compose services to be running.
"""

import os

import pytest
import pytest_asyncio

from src.core.storage.base import (
    CacheConfig,
    DatabaseConfig,
    FileStorageConfig,
    VectorStoreConfig,
)
from src.core.storage.file_storage import FileStorage
from src.core.storage.postgres import Database
from src.core.storage.redis_cache import Cache
from src.core.storage.vector_store import VectorStore


# Use test database to avoid polluting production data
TEST_DB = "assistant_test"
TEST_REDIS_DB = 15  # Use separate Redis DB for tests
TEST_BUCKET = "assistant-test"
TEST_COLLECTION_PREFIX = "test_"


@pytest.fixture
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


@pytest.fixture
def cache_config() -> CacheConfig:
    """Redis cache configuration for tests."""
    return CacheConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=TEST_REDIS_DB,
        password=os.getenv("REDIS_PASSWORD", ""),
        default_ttl=60,
        max_connections=5,
    )


@pytest.fixture
def vector_store_config() -> VectorStoreConfig:
    """Vector store configuration for tests."""
    return VectorStoreConfig(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
        grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
        collection_prefix=TEST_COLLECTION_PREFIX,
    )


@pytest.fixture
def file_storage_config() -> FileStorageConfig:
    """File storage configuration for tests."""
    return FileStorageConfig(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        bucket=TEST_BUCKET,
        secure=False,
        region="us-east-1",
    )


@pytest_asyncio.fixture
async def database(database_config: DatabaseConfig) -> Database:
    """Provide a connected database instance."""
    db = Database(database_config)
    await db.connect()
    yield db
    await db.disconnect()


@pytest_asyncio.fixture
async def cache(cache_config: CacheConfig) -> Cache:
    """Provide a connected cache instance."""
    c = Cache(cache_config)
    await c.connect()
    # Clear test database before each test
    await c.flush_db()
    yield c
    await c.disconnect()


@pytest_asyncio.fixture
async def vector_store(vector_store_config: VectorStoreConfig) -> VectorStore:
    """Provide a connected vector store instance."""
    store = VectorStore(vector_store_config)
    await store.connect()
    yield store
    await store.disconnect()


@pytest_asyncio.fixture
async def file_storage(file_storage_config: FileStorageConfig) -> FileStorage:
    """Provide a connected file storage instance."""
    storage = FileStorage(file_storage_config)
    await storage.connect()
    yield storage
    await storage.disconnect()
