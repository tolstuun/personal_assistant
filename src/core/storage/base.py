"""
Base interfaces for storage components.

All storage implementations must follow these interfaces.
This ensures we can swap implementations without changing agent code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# PostgreSQL Base
# =============================================================================


@dataclass
class DatabaseConfig:
    """Configuration for PostgreSQL database."""

    host: str = "localhost"
    port: int = 5432
    database: str = "assistant"
    user: str = "assistant"
    password: str = "assistant"
    pool_size: int = 5
    pool_max_overflow: int = 10
    echo: bool = False


class BaseDatabase(ABC):
    """
    Abstract base class for database operations.

    Usage:
        db = SomeDatabase(config)
        await db.connect()

        async with db.session() as session:
            result = await session.execute(query)

        await db.disconnect()
    """

    def __init__(self, config: DatabaseConfig):
        """Initialize with configuration."""
        self.config = config

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the database."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close all database connections."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if database is reachable."""
        pass

    @abstractmethod
    def session(self) -> Any:
        """Return a session context manager."""
        pass


# =============================================================================
# Redis Cache Base
# =============================================================================


@dataclass
class CacheConfig:
    """Configuration for Redis cache."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    default_ttl: int = 3600
    max_connections: int = 10


class BaseCache(ABC):
    """
    Abstract base class for cache operations.

    Usage:
        cache = SomeCache(config)
        await cache.connect()

        await cache.set("key", "value", ttl=3600)
        value = await cache.get("key")

        await cache.disconnect()
    """

    def __init__(self, config: CacheConfig):
        """Initialize with configuration."""
        self.config = config

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to cache service."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close all cache connections."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if cache service is reachable."""
        pass

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Get value by key. Returns None if not found."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set key-value pair with optional TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    async def get_json(self, key: str) -> dict[str, Any] | list | None:
        """Get JSON value by key. Automatically deserializes."""
        pass

    @abstractmethod
    async def set_json(
        self, key: str, value: dict[str, Any] | list, ttl: int | None = None
    ) -> None:
        """Set JSON value. Automatically serializes."""
        pass


# =============================================================================
# Vector Store Base
# =============================================================================


@dataclass
class VectorStoreConfig:
    """Configuration for vector store."""

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    collection_prefix: str = "assistant_"
    api_key: str = ""


@dataclass
class VectorDocument:
    """A document with its embedding for vector storage."""

    id: str
    embedding: list[float]
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    """A single search result from vector store."""

    id: str
    score: float
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseVectorStore(ABC):
    """
    Abstract base class for vector store operations.

    Usage:
        store = SomeVectorStore(config)
        await store.connect()

        await store.upsert("knowledge", [VectorDocument(...)])
        results = await store.search("knowledge", embedding, limit=10)

        await store.disconnect()
    """

    def __init__(self, config: VectorStoreConfig):
        """Initialize with configuration."""
        self.config = config

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to vector store."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to vector store."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if vector store is reachable."""
        pass

    @abstractmethod
    async def create_collection(
        self, name: str, vector_size: int, distance: str = "cosine"
    ) -> None:
        """Create a collection for storing vectors."""
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        pass

    @abstractmethod
    async def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        pass

    @abstractmethod
    async def upsert(self, collection: str, documents: list[VectorDocument]) -> None:
        """Insert or update documents in collection."""
        pass

    @abstractmethod
    async def search(
        self,
        collection: str,
        embedding: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        """Search for similar vectors."""
        pass

    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> None:
        """Delete documents by IDs."""
        pass


# =============================================================================
# File Storage Base
# =============================================================================


@dataclass
class FileStorageConfig:
    """Configuration for file storage (S3/MinIO)."""

    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "assistant"
    secure: bool = False
    region: str = "us-east-1"


@dataclass
class FileInfo:
    """Information about a stored file."""

    key: str
    size: int
    last_modified: str
    content_type: str = ""


class BaseFileStorage(ABC):
    """
    Abstract base class for file storage operations.

    Usage:
        storage = SomeFileStorage(config)
        await storage.connect()

        url = await storage.upload("path/to/file.pdf", content)
        content = await storage.download("path/to/file.pdf")

        await storage.disconnect()
    """

    def __init__(self, config: FileStorageConfig):
        """Initialize with configuration."""
        self.config = config

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection and ensure bucket exists."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to file storage."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if file storage is reachable."""
        pass

    @abstractmethod
    async def upload(
        self, key: str, content: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file. Returns the file key."""
        pass

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download file content."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    async def get_info(self, key: str) -> FileInfo:
        """Get file metadata."""
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "") -> list[FileInfo]:
        """List files with optional prefix filter."""
        pass

    @abstractmethod
    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """Generate presigned URL for direct download."""
        pass
