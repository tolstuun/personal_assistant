"""
Tests for Redis cache.

Requires docker-compose redis service to be running.
Run: docker-compose up -d redis
"""

import pytest

from src.core.storage.redis_cache import Cache


@pytest.mark.asyncio
async def test_cache_connection(cache: Cache) -> None:
    """Test that cache connects successfully."""
    assert await cache.health_check() is True


@pytest.mark.asyncio
async def test_cache_set_get(cache: Cache) -> None:
    """Test basic set and get operations."""
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value"


@pytest.mark.asyncio
async def test_cache_get_nonexistent(cache: Cache) -> None:
    """Test getting a key that doesn't exist."""
    value = await cache.get("nonexistent_key")
    assert value is None


@pytest.mark.asyncio
async def test_cache_delete(cache: Cache) -> None:
    """Test deleting a key."""
    await cache.set("to_delete", "value")
    assert await cache.exists("to_delete") is True

    deleted = await cache.delete("to_delete")
    assert deleted is True
    assert await cache.exists("to_delete") is False

    # Deleting nonexistent key
    deleted = await cache.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_cache_exists(cache: Cache) -> None:
    """Test checking if key exists."""
    await cache.set("exists_key", "value")

    assert await cache.exists("exists_key") is True
    assert await cache.exists("not_exists_key") is False


@pytest.mark.asyncio
async def test_cache_json_operations(cache: Cache) -> None:
    """Test JSON serialization and deserialization."""
    data = {
        "user_id": 123,
        "name": "John Doe",
        "settings": {"theme": "dark", "notifications": True},
    }

    await cache.set_json("user:123", data)
    result = await cache.get_json("user:123")

    assert result == data
    assert result["user_id"] == 123
    assert result["settings"]["theme"] == "dark"


@pytest.mark.asyncio
async def test_cache_json_list(cache: Cache) -> None:
    """Test JSON with list data."""
    data = [1, 2, 3, "four", {"five": 5}]

    await cache.set_json("list_key", data)
    result = await cache.get_json("list_key")

    assert result == data


@pytest.mark.asyncio
async def test_cache_json_nonexistent(cache: Cache) -> None:
    """Test getting nonexistent JSON key."""
    result = await cache.get_json("nonexistent_json")
    assert result is None


@pytest.mark.asyncio
async def test_cache_incr_decr(cache: Cache) -> None:
    """Test increment and decrement operations."""
    # Increment creates key if not exists
    value = await cache.incr("counter")
    assert value == 1

    value = await cache.incr("counter")
    assert value == 2

    value = await cache.decr("counter")
    assert value == 1


@pytest.mark.asyncio
async def test_cache_ttl(cache: Cache) -> None:
    """Test TTL operations."""
    await cache.set("ttl_key", "value", ttl=100)

    ttl = await cache.ttl("ttl_key")
    assert 0 < ttl <= 100

    # Set new TTL
    await cache.expire("ttl_key", 50)
    ttl = await cache.ttl("ttl_key")
    assert 0 < ttl <= 50


@pytest.mark.asyncio
async def test_cache_keys_pattern(cache: Cache) -> None:
    """Test getting keys by pattern."""
    await cache.set("user:1", "a")
    await cache.set("user:2", "b")
    await cache.set("session:1", "c")

    user_keys = await cache.keys("user:*")
    assert len(user_keys) == 2
    assert "user:1" in user_keys
    assert "user:2" in user_keys

    session_keys = await cache.keys("session:*")
    assert len(session_keys) == 1
    assert "session:1" in session_keys
