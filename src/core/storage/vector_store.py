"""
Vector store implementation using Qdrant.

Provides vector similarity search for RAG (retrieval-augmented generation).
Supports storing documents with embeddings and semantic search.
"""

import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.core.config.loader import get_config
from src.core.storage.base import (
    BaseVectorStore,
    VectorDocument,
    VectorSearchResult,
    VectorStoreConfig,
)
from src.core.storage.exceptions import ConfigurationError, ConnectionError, NotFoundError

logger = logging.getLogger(__name__)


# Distance metric mapping
DISTANCE_MAP = {
    "cosine": Distance.COSINE,
    "euclidean": Distance.EUCLID,
    "dot": Distance.DOT,
}


class VectorStore(BaseVectorStore):
    """
    Qdrant vector store implementation.

    Usage:
        store = VectorStore(config)
        await store.connect()

        # Create collection
        await store.create_collection("knowledge", vector_size=1536)

        # Add documents
        await store.upsert("knowledge", [
            VectorDocument(
                id="doc1",
                embedding=[0.1, 0.2, ...],
                text="Some text",
                metadata={"source": "wikipedia"}
            )
        ])

        # Search
        results = await store.search("knowledge", query_embedding, limit=5)

        await store.disconnect()
    """

    def __init__(self, config: VectorStoreConfig):
        """Initialize vector store with configuration."""
        super().__init__(config)
        self._client: AsyncQdrantClient | None = None

    def _get_collection_name(self, name: str) -> str:
        """Get full collection name with prefix."""
        return f"{self.config.collection_prefix}{name}"

    async def connect(self) -> None:
        """Establish connection to Qdrant."""
        if self._client is not None:
            return

        try:
            self._client = AsyncQdrantClient(
                host=self.config.host,
                port=self.config.port,
                grpc_port=self.config.grpc_port,
                api_key=self.config.api_key if self.config.api_key else None,
            )
            # Test connection
            await self._client.get_collections()
            logger.info(f"Connected to Qdrant at {self.config.host}:{self.config.port}")
        except Exception as e:
            self._client = None
            raise ConnectionError(f"Failed to connect to Qdrant: {e}") from e

    async def disconnect(self) -> None:
        """Close connection to Qdrant."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Qdrant")

    async def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        if self._client is None:
            return False

        try:
            await self._client.get_collections()
            return True
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            return False

    def _get_client(self) -> AsyncQdrantClient:
        """Get Qdrant client, raising if not connected."""
        if self._client is None:
            raise ConnectionError("Vector store not connected. Call connect() first.")
        return self._client

    async def create_collection(
        self, name: str, vector_size: int, distance: str = "cosine"
    ) -> None:
        """Create a collection for storing vectors."""
        client = self._get_client()
        collection_name = self._get_collection_name(name)

        if distance not in DISTANCE_MAP:
            raise ValueError(f"Invalid distance metric: {distance}. Use: cosine, euclidean, dot")

        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=DISTANCE_MAP[distance],
            ),
        )
        logger.info(f"Created collection: {collection_name}")

    async def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        client = self._get_client()
        collection_name = self._get_collection_name(name)

        await client.delete_collection(collection_name=collection_name)
        logger.info(f"Deleted collection: {collection_name}")

    async def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        client = self._get_client()
        collection_name = self._get_collection_name(name)

        try:
            await client.get_collection(collection_name)
            return True
        except Exception:
            return False

    async def upsert(self, collection: str, documents: list[VectorDocument]) -> None:
        """Insert or update documents in collection."""
        client = self._get_client()
        collection_name = self._get_collection_name(collection)

        points = [
            PointStruct(
                id=doc.id,
                vector=doc.embedding,
                payload={
                    "text": doc.text,
                    **doc.metadata,
                },
            )
            for doc in documents
        ]

        await client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.debug(f"Upserted {len(documents)} documents to {collection_name}")

    async def search(
        self,
        collection: str,
        embedding: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        """Search for similar vectors."""
        client = self._get_client()
        collection_name = self._get_collection_name(collection)

        results = await client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            VectorSearchResult(
                id=str(result.id),
                score=result.score,
                text=result.payload.get("text", "") if result.payload else "",
                metadata={
                    k: v
                    for k, v in (result.payload or {}).items()
                    if k != "text"
                },
            )
            for result in results
        ]

    async def delete(self, collection: str, ids: list[str]) -> None:
        """Delete documents by IDs."""
        client = self._get_client()
        collection_name = self._get_collection_name(collection)

        await client.delete(
            collection_name=collection_name,
            points_selector=ids,
        )
        logger.debug(f"Deleted {len(ids)} documents from {collection_name}")

    async def get_collection_info(self, name: str) -> dict[str, Any]:
        """Get collection metadata and statistics."""
        client = self._get_client()
        collection_name = self._get_collection_name(name)

        info = await client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.value,
        }


def _load_config() -> VectorStoreConfig:
    """Load vector store configuration from config files."""
    config = get_config()
    qdrant_config = config.get("qdrant", {})

    if not qdrant_config:
        raise ConfigurationError("Qdrant configuration not found")

    return VectorStoreConfig(
        host=qdrant_config.get("host", "localhost"),
        port=int(qdrant_config.get("port", 6333)),
        grpc_port=int(qdrant_config.get("grpc_port", 6334)),
        collection_prefix=qdrant_config.get("collection_prefix", "assistant_"),
        api_key=qdrant_config.get("api_key", ""),
    )


# Global vector store instance
_vector_store_instance: VectorStore | None = None


async def get_vector_store() -> VectorStore:
    """
    Get the global vector store instance.

    Creates and connects the instance on first call.
    Subsequent calls return the same instance.

    Returns:
        Connected VectorStore instance.
    """
    global _vector_store_instance

    if _vector_store_instance is None:
        config = _load_config()
        _vector_store_instance = VectorStore(config)
        await _vector_store_instance.connect()

    return _vector_store_instance


async def close_vector_store() -> None:
    """Close the global vector store instance."""
    global _vector_store_instance

    if _vector_store_instance is not None:
        await _vector_store_instance.disconnect()
        _vector_store_instance = None
