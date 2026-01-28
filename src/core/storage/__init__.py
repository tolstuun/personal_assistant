"""
Storage module.

Provides unified access to all storage backends:
- PostgreSQL for relational data
- Redis for caching
- Qdrant for vector search
- MinIO/S3 for file storage

Usage:
    from src.core.storage import get_db, get_cache, get_vector_store, get_file_storage

    # PostgreSQL
    db = await get_db()
    async with db.session() as session:
        result = await session.execute(query)

    # Redis cache
    cache = await get_cache()
    await cache.set("key", "value")
    value = await cache.get("key")

    # Vector store
    store = await get_vector_store()
    await store.upsert("collection", documents)
    results = await store.search("collection", embedding)

    # File storage
    storage = await get_file_storage()
    await storage.upload("path/to/file.pdf", content)
    content = await storage.download("path/to/file.pdf")
"""

# Base classes and types
from src.core.storage.base import (
    BaseCache,
    BaseDatabase,
    BaseFileStorage,
    BaseVectorStore,
    CacheConfig,
    DatabaseConfig,
    FileInfo,
    FileStorageConfig,
    VectorDocument,
    VectorSearchResult,
    VectorStoreConfig,
)

# Exceptions
from src.core.storage.exceptions import (
    ConfigurationError,
    ConnectionError,
    DuplicateError,
    NotFoundError,
    StorageError,
)

# File storage
from src.core.storage.file_storage import (
    FileStorage,
    close_file_storage,
    get_file_storage,
)

# PostgreSQL
from src.core.storage.postgres import (
    Base,
    Database,
    close_db,
    get_db,
)

# Redis cache
from src.core.storage.redis_cache import (
    Cache,
    close_cache,
    get_cache,
)

# Vector store
from src.core.storage.vector_store import (
    VectorStore,
    close_vector_store,
    get_vector_store,
)

__all__ = [
    # Base classes
    "BaseDatabase",
    "BaseCache",
    "BaseVectorStore",
    "BaseFileStorage",
    # Config types
    "DatabaseConfig",
    "CacheConfig",
    "VectorStoreConfig",
    "FileStorageConfig",
    # Data types
    "VectorDocument",
    "VectorSearchResult",
    "FileInfo",
    # Exceptions
    "StorageError",
    "ConnectionError",
    "NotFoundError",
    "DuplicateError",
    "ConfigurationError",
    # PostgreSQL
    "Database",
    "Base",
    "get_db",
    "close_db",
    # Redis
    "Cache",
    "get_cache",
    "close_cache",
    # Vector store
    "VectorStore",
    "get_vector_store",
    "close_vector_store",
    # File storage
    "FileStorage",
    "get_file_storage",
    "close_file_storage",
]
