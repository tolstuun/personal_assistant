"""
Redis cache implementation.

Provides caching, JSON storage, and basic pub/sub operations.
Uses redis-py with async support.
"""

import json
import logging
from typing import Any

import redis.asyncio as redis

from src.core.config.loader import get_config
from src.core.storage.base import BaseCache, CacheConfig
from src.core.storage.exceptions import ConfigurationError, ConnectionError

logger = logging.getLogger(__name__)


class Cache(BaseCache):
    """
    Redis cache implementation.

    Usage:
        cache = Cache(config)
        await cache.connect()

        await cache.set("user:123", "John", ttl=3600)
        name = await cache.get("user:123")

        await cache.set_json("session:abc", {"user_id": 123})
        session = await cache.get_json("session:abc")

        await cache.disconnect()
    """

    def __init__(self, config: CacheConfig):
        """Initialize cache with configuration."""
        super().__init__(config)
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._client is not None:
            return

        try:
            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password if self.config.password else None,
                max_connections=self.config.max_connections,
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            logger.info(f"Connected to Redis at {self.config.host}:{self.config.port}")
        except Exception as e:
            self._client = None
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Disconnected from Redis")

    async def health_check(self) -> bool:
        """Check if Redis is reachable."""
        if self._client is None:
            return False

        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    def _get_client(self) -> redis.Redis:
        """Get Redis client, raising if not connected."""
        if self._client is None:
            raise ConnectionError("Cache not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> str | None:
        """Get string value by key. Returns None if not found."""
        client = self._get_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set string value with optional TTL in seconds."""
        client = self._get_client()
        ttl = ttl or self.config.default_ttl
        await client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed."""
        client = self._get_client()
        result = await client.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = self._get_client()
        result = await client.exists(key)
        return result > 0

    async def get_json(self, key: str) -> dict[str, Any] | list | None:
        """Get JSON value by key. Automatically deserializes."""
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode JSON for key: {key}")
            return None

    async def set_json(
        self, key: str, value: dict[str, Any] | list, ttl: int | None = None
    ) -> None:
        """Set JSON value. Automatically serializes."""
        json_str = json.dumps(value)
        await self.set(key, json_str, ttl)

    async def incr(self, key: str) -> int:
        """Increment integer value. Creates key with value 1 if not exists."""
        client = self._get_client()
        return await client.incr(key)

    async def decr(self, key: str) -> int:
        """Decrement integer value."""
        client = self._get_client()
        return await client.decr(key)

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key. Returns True if key exists."""
        client = self._get_client()
        return await client.expire(key, ttl)

    async def ttl(self, key: str) -> int:
        """Get remaining TTL in seconds. Returns -1 if no TTL, -2 if key doesn't exist."""
        client = self._get_client()
        return await client.ttl(key)

    async def keys(self, pattern: str = "*") -> list[str]:
        """Get all keys matching pattern. Use with caution in production."""
        client = self._get_client()
        return await client.keys(pattern)

    async def flush_db(self) -> None:
        """Delete all keys in current database. Use with caution."""
        client = self._get_client()
        await client.flushdb()
        logger.warning("Redis database flushed")


def _load_config() -> CacheConfig:
    """Load cache configuration from config files."""
    config = get_config()
    redis_config = config.get("redis", {})

    if not redis_config:
        raise ConfigurationError("Redis configuration not found")

    return CacheConfig(
        host=redis_config.get("host", "localhost"),
        port=int(redis_config.get("port", 6379)),
        db=int(redis_config.get("db", 0)),
        password=redis_config.get("password", ""),
        default_ttl=int(redis_config.get("default_ttl", 3600)),
        max_connections=int(redis_config.get("max_connections", 10)),
    )


# Global cache instance
_cache_instance: Cache | None = None


async def get_cache() -> Cache:
    """
    Get the global cache instance.

    Creates and connects the instance on first call.
    Subsequent calls return the same instance.

    Returns:
        Connected Cache instance.
    """
    global _cache_instance

    if _cache_instance is None:
        config = _load_config()
        _cache_instance = Cache(config)
        await _cache_instance.connect()

    return _cache_instance


async def close_cache() -> None:
    """Close the global cache instance."""
    global _cache_instance

    if _cache_instance is not None:
        await _cache_instance.disconnect()
        _cache_instance = None
