"""Integration tests for ValkeyCacheStorage.

These tests require a running Valkey server.
Skip if Valkey is not available.

To run locally::

    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest

    pytest -v -k test_valkey_cache_integration
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.integration

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD", None)


def _valkey_available() -> bool:
    """Check if Valkey is available."""
    try:
        import asyncio

        from glide import GlideClient, GlideClientConfiguration, NodeAddress

        async def _check():
            config = GlideClientConfiguration(
                addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)]
            )
            client = await GlideClient.create(config)
            await client.ping()
            await client.close()
            return True

        return asyncio.run(_check())
    except Exception:
        return False


if not _valkey_available():
    pytest.skip("Valkey server not available", allow_module_level=True)

from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage  # noqa: E402


class MockCacheKey:
    """Mock cache key for integration testing."""

    def __init__(self, key_str: str):
        self._key_str = key_str

    def get_hash_bytes(self) -> bytes:
        return self._key_str.encode()

    def serialize(self) -> bytes:
        return f"key_data:{self._key_str}".encode()

    def __hash__(self):
        return hash(self._key_str)


class MockCacheValue:
    """Mock cache value for integration testing."""

    def __init__(self, value_str: str):
        self._value_str = value_str

    def serialize(self) -> bytes:
        return f"value_data:{self._value_str}".encode()


@pytest.fixture
def storage():
    """Create a ValkeyCacheStorage for integration testing."""
    prefix = f"inttest_cache_{uuid.uuid4().hex[:8]}:"
    s = ValkeyCacheStorage(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        password=VALKEY_PASSWORD,
        key_prefix=prefix,
        ttl_seconds=60,
    )
    yield s
    # Cleanup
    try:
        cursor = "0"
        while True:
            result = s._run_async(
                s.client.custom_command(
                    ["SCAN", cursor, "MATCH", f"{prefix}*", "COUNT", "100"]
                )
            )
            if isinstance(result, (list, tuple)) and len(result) == 2:
                cursor = result[0]
                if isinstance(cursor, bytes):
                    cursor = cursor.decode()
                keys = result[1]
                if keys:
                    key_list = [k.decode() if isinstance(k, bytes) else k for k in keys]
                    s._run_async(s.client.delete(key_list))
            else:
                break
            if cursor == "0":
                break
    except Exception:
        pass


class TestValkeyCacheStorageIntegration:
    """Integration tests for ValkeyCacheStorage."""

    def test_set_and_get(self, storage):
        """Test basic set and get."""
        key = MockCacheKey("int_test_1")
        value = MockCacheValue("hello world")

        storage.set(key, value)
        result = storage.get(key)

        assert result is not None
        assert result.key_data == b"key_data:int_test_1"
        assert result.value_data == b"value_data:hello world"

    def test_get_miss(self, storage):
        """Test get on non-existent key returns None."""
        key = MockCacheKey("nonexistent_key")
        result = storage.get(key)
        assert result is None

    def test_exists(self, storage):
        """Test exists check."""
        key = MockCacheKey("exists_test")
        value = MockCacheValue("data")

        assert storage.exists(key) is False
        storage.set(key, value)
        assert storage.exists(key) is True

    def test_overwrite(self, storage):
        """Test overwriting an existing key."""
        key = MockCacheKey("overwrite_test")
        value1 = MockCacheValue("first")
        value2 = MockCacheValue("second")

        storage.set(key, value1)
        storage.set(key, value2)

        result = storage.get(key)
        assert result is not None
        assert result.value_data == b"value_data:second"

    def test_multiple_keys(self, storage):
        """Test storing and retrieving multiple keys."""
        keys_values = [
            (MockCacheKey(f"multi_{i}"), MockCacheValue(f"val_{i}")) for i in range(5)
        ]

        for key, value in keys_values:
            storage.set(key, value)

        for i, (key, _) in enumerate(keys_values):
            result = storage.get(key)
            assert result is not None
            assert result.value_data == f"value_data:val_{i}".encode()

    def test_ttl_is_set(self, storage):
        """Test that TTL is applied to keys."""
        key = MockCacheKey("ttl_test")
        value = MockCacheValue("expires")

        storage.set(key, value)

        valkey_key = storage._make_key(key)
        ttl = storage._run_async(storage.client.ttl(valkey_key))
        assert ttl > 0
        assert ttl <= 60

    @pytest.mark.asyncio
    async def test_aset_and_aget(self, storage):
        """Test async set and get."""
        key = MockCacheKey("async_int_test")
        value = MockCacheValue("async hello")

        await storage.aset(key, value)
        result = await storage.aget(key)

        assert result is not None
        assert result.key_data == b"key_data:async_int_test"
        assert result.value_data == b"value_data:async hello"

    @pytest.mark.asyncio
    async def test_aget_miss(self, storage):
        """Test async get on non-existent key returns None."""
        key = MockCacheKey("async_nonexistent")
        result = await storage.aget(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_aset_with_ttl(self, storage):
        """Test async set respects TTL."""
        key = MockCacheKey("async_ttl_test")
        value = MockCacheValue("async expires")

        await storage.aset(key, value)

        valkey_key = storage._make_key(key)
        client = await storage._get_async_client()
        ttl = await client.ttl(valkey_key)
        assert ttl > 0
        assert ttl <= 60

    def test_close(self, storage):
        """Test close releases resources without error."""
        key = MockCacheKey("close_test")
        value = MockCacheValue("data")
        storage.set(key, value)

        storage.close()
        assert storage._client is None
