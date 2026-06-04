"""Unit tests for ValkeyCacheStorage.

These tests use mocked valkey-glide client and do not require a running Valkey server.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from dbgpt.core.interface.cache import RetrievalPolicy
from dbgpt.storage.cache.storage.base import StorageItem
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


class MockCacheKey:
    """Mock cache key for testing."""

    def __init__(self, key_str: str = "test_key"):
        self._key_str = key_str

    def get_hash_bytes(self) -> bytes:
        return self._key_str.encode()

    def serialize(self) -> bytes:
        return self._key_str.encode()

    def __hash__(self):
        return hash(self._key_str)


class MockCacheValue:
    """Mock cache value for testing."""

    def __init__(self, value_str: str = "test_value"):
        self._value_str = value_str

    def serialize(self) -> bytes:
        return self._value_str.encode()


class MockCacheConfig:
    """Mock cache config for testing."""

    def __init__(self, retrieval_policy=RetrievalPolicy.EXACT_MATCH):
        self.retrieval_policy = retrieval_policy


@pytest.fixture
def mock_client():
    """Create a mock Valkey client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=None)
    client.exists = AsyncMock(return_value=0)
    return client


@pytest.fixture
def valkey_cache(mock_client):
    """Create a ValkeyCacheStorage with mocked client."""
    with patch.object(ValkeyCacheStorage, "_create_client", return_value=mock_client):
        storage = ValkeyCacheStorage(
            host="localhost",
            port=6379,
            key_prefix="test_cache:",
            ttl_seconds=None,
        )
        storage._client = mock_client
        return storage


class TestValkeyCacheStorageInit:
    """Tests for initialization."""

    def test_default_config(self, mock_client):
        """Test default configuration values."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage()
            assert storage._host == "localhost"
            assert storage._port == 6379
            assert storage._key_prefix == "dbgpt_cache:"
            assert storage._ttl_seconds is None

    def test_custom_config(self, valkey_cache):
        """Test custom configuration."""
        assert valkey_cache._host == "localhost"
        assert valkey_cache._port == 6379
        assert valkey_cache._key_prefix == "test_cache:"

    def test_support_async(self, valkey_cache):
        """Test that async is supported."""
        assert valkey_cache.support_async() is True


class TestValkeyCacheStorageCheckConfig:
    """Tests for check_config."""

    def test_valid_config(self, valkey_cache):
        """Test valid config passes."""
        config = MockCacheConfig(RetrievalPolicy.EXACT_MATCH)
        assert valkey_cache.check_config(config) is True

    def test_none_config(self, valkey_cache):
        """Test None config passes."""
        assert valkey_cache.check_config(None) is True

    def test_invalid_policy_raises(self, valkey_cache):
        """Test invalid retrieval policy raises ValueError."""
        config = MockCacheConfig(retrieval_policy="SIMILARITY")
        with pytest.raises(ValueError, match="EXACT_MATCH"):
            valkey_cache.check_config(config)

    def test_invalid_policy_no_raise(self, valkey_cache):
        """Test invalid retrieval policy returns False when raise_error=False."""
        config = MockCacheConfig(retrieval_policy="SIMILARITY")
        assert valkey_cache.check_config(config, raise_error=False) is False


class TestValkeyCacheStorageGet:
    """Tests for get operations."""

    def test_get_miss(self, valkey_cache, mock_client):
        """Test cache miss returns None."""
        mock_client.get = AsyncMock(return_value=None)
        key = MockCacheKey("missing_key")
        result = valkey_cache.get(key)
        assert result is None

    def test_get_hit(self, valkey_cache, mock_client):
        """Test cache hit returns StorageItem."""
        key = MockCacheKey("hit_key")
        value = MockCacheValue("hit_value")
        item = StorageItem.build_from_kv(key, value)
        serialized = item.serialize()

        mock_client.get = AsyncMock(return_value=serialized)
        result = valkey_cache.get(key)

        assert result is not None
        assert result.key_data == b"hit_key"
        assert result.value_data == b"hit_value"

    def test_get_corrupt_data(self, valkey_cache, mock_client):
        """Test corrupt data returns None gracefully."""
        mock_client.get = AsyncMock(return_value=b"not_valid_msgpack")
        key = MockCacheKey("corrupt")
        result = valkey_cache.get(key)
        assert result is None


class TestValkeyCacheStorageSet:
    """Tests for set operations."""

    def test_set_without_ttl(self, valkey_cache, mock_client):
        """Test setting a value without TTL."""
        key = MockCacheKey("set_key")
        value = MockCacheValue("set_value")

        valkey_cache.set(key, value)

        mock_client.set.assert_called_once()
        call_args = mock_client.set.call_args[0]
        assert call_args[0] == "test_cache:" + b"set_key".hex()
        assert isinstance(call_args[1], bytes)

    def test_set_with_ttl(self, mock_client):
        """Test setting a value with TTL."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(
                host="localhost",
                port=6379,
                key_prefix="test_cache:",
                ttl_seconds=3600,
            )
            storage._client = mock_client

            key = MockCacheKey("ttl_key")
            value = MockCacheValue("ttl_value")

            storage.set(key, value)
            mock_client.set.assert_called_once()
            call_kwargs = mock_client.set.call_args[1]
            assert "expiry" in call_kwargs


class TestValkeyCacheStorageExists:
    """Tests for exists operation."""

    def test_exists_true(self, valkey_cache, mock_client):
        """Test exists returns True when key is present."""
        mock_client.exists = AsyncMock(return_value=1)
        key = MockCacheKey("existing")
        assert valkey_cache.exists(key) is True

    def test_exists_false(self, valkey_cache, mock_client):
        """Test exists returns False when key is absent."""
        mock_client.exists = AsyncMock(return_value=0)
        key = MockCacheKey("missing")
        assert valkey_cache.exists(key) is False


class TestValkeyCacheStorageKeyGeneration:
    """Tests for key generation."""

    def test_make_key(self, valkey_cache):
        """Test key generation includes prefix and hex hash."""
        key = MockCacheKey("my_key")
        result = valkey_cache._make_key(key)
        assert result == "test_cache:" + b"my_key".hex()

    def test_different_keys_produce_different_valkey_keys(self, valkey_cache):
        """Test that different cache keys produce different Valkey keys."""
        key1 = MockCacheKey("key_a")
        key2 = MockCacheKey("key_b")
        assert valkey_cache._make_key(key1) != valkey_cache._make_key(key2)


class TestValkeyCacheStorageAsync:
    """Tests for async operations."""

    @pytest.mark.asyncio
    async def test_aget_miss(self, valkey_cache, mock_client):
        """Test async cache miss returns None."""
        mock_client.get = AsyncMock(return_value=None)
        valkey_cache._async_client = mock_client
        valkey_cache._async_loop = asyncio.get_running_loop()
        key = MockCacheKey("async_missing")
        result = await valkey_cache.aget(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_aget_hit(self, valkey_cache, mock_client):
        """Test async cache hit returns StorageItem."""
        key = MockCacheKey("async_hit")
        value = MockCacheValue("async_value")
        item = StorageItem.build_from_kv(key, value)
        serialized = item.serialize()

        mock_client.get = AsyncMock(return_value=serialized)
        valkey_cache._async_client = mock_client
        valkey_cache._async_loop = asyncio.get_running_loop()
        result = await valkey_cache.aget(key)

        assert result is not None
        assert result.key_data == b"async_hit"
        assert result.value_data == b"async_value"

    @pytest.mark.asyncio
    async def test_aget_corrupt_data(self, valkey_cache, mock_client):
        """Test async corrupt data returns None gracefully."""
        mock_client.get = AsyncMock(return_value=b"not_valid_msgpack")
        valkey_cache._async_client = mock_client
        valkey_cache._async_loop = asyncio.get_running_loop()
        key = MockCacheKey("async_corrupt")
        result = await valkey_cache.aget(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_aset_without_ttl(self, valkey_cache, mock_client):
        """Test async setting a value without TTL."""
        valkey_cache._async_client = mock_client
        valkey_cache._async_loop = asyncio.get_running_loop()
        key = MockCacheKey("async_set_key")
        value = MockCacheValue("async_set_value")

        await valkey_cache.aset(key, value)

        mock_client.set.assert_called_once()
        call_args = mock_client.set.call_args[0]
        assert call_args[0] == "test_cache:" + b"async_set_key".hex()
        assert isinstance(call_args[1], bytes)

    @pytest.mark.asyncio
    async def test_aset_with_ttl(self, mock_client):
        """Test async setting a value with TTL."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(
                host="localhost",
                port=6379,
                key_prefix="test_cache:",
                ttl_seconds=3600,
            )
            storage._client = mock_client
            storage._async_client = mock_client
            storage._async_loop = asyncio.get_running_loop()

            key = MockCacheKey("async_ttl_key")
            value = MockCacheValue("async_ttl_value")

            await storage.aset(key, value)
            mock_client.set.assert_called_once()
            call_kwargs = mock_client.set.call_args[1]
            assert "expiry" in call_kwargs


class TestValkeyCacheStorageClose:
    """Tests for close/cleanup."""

    def test_close_releases_resources(self, valkey_cache, mock_client):
        """Test close releases client and event loop."""
        mock_client.close = AsyncMock()
        # Access client to ensure it's set
        _ = valkey_cache.client
        valkey_cache.close()

        assert valkey_cache._client is None
        assert valkey_cache._loop.is_closed()

    def test_close_idempotent(self, valkey_cache, mock_client):
        """Test calling close multiple times is safe."""
        mock_client.close = AsyncMock()
        valkey_cache.close()
        # Second call should not raise
        valkey_cache.close()

    def test_close_releases_async_client(self, valkey_cache, mock_client):
        """Test close properly closes _async_client (not just sets to None)."""
        async_client = AsyncMock()
        async_client.close = AsyncMock()
        valkey_cache._async_client = async_client

        valkey_cache.close()

        async_client.close.assert_called_once()
        assert valkey_cache._async_client is None


class TestValkeyCacheStorageTTLZero:
    """Tests for TTL=0 edge case (falsy but valid)."""

    def test_set_with_ttl_zero(self, mock_client):
        """Test that ttl_seconds=0 still applies TTL (not skipped as falsy)."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(
                host="localhost",
                port=6379,
                key_prefix="test_cache:",
                ttl_seconds=0,
            )
            storage._client = mock_client

            key = MockCacheKey("zero_ttl_key")
            value = MockCacheValue("zero_ttl_value")

            storage.set(key, value)
            mock_client.set.assert_called_once()
            call_kwargs = mock_client.set.call_args[1]
            assert "expiry" in call_kwargs

    @pytest.mark.asyncio
    async def test_aset_with_ttl_zero(self, mock_client):
        """Test that async ttl_seconds=0 still applies TTL."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(
                host="localhost",
                port=6379,
                key_prefix="test_cache:",
                ttl_seconds=0,
            )
            storage._client = mock_client
            storage._async_client = mock_client
            storage._async_loop = asyncio.get_running_loop()

            key = MockCacheKey("async_zero_ttl_key")
            value = MockCacheValue("async_zero_ttl_value")

            await storage.aset(key, value)
            mock_client.set.assert_called_once()
            call_kwargs = mock_client.set.call_args[1]
            assert "expiry" in call_kwargs


class TestValkeyCacheStorageRequestTimeout:
    """Tests for request_timeout configuration."""

    def test_default_request_timeout(self, mock_client):
        """Test default request_timeout is 5000ms."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(host="localhost", port=6379)
            assert storage._request_timeout == 5000

    def test_custom_request_timeout(self, mock_client):
        """Test custom request_timeout is stored."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(
                host="localhost", port=6379, request_timeout=10000
            )
            assert storage._request_timeout == 10000

    def test_none_request_timeout(self, mock_client):
        """Test None request_timeout disables timeout."""
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(
                host="localhost", port=6379, request_timeout=None
            )
            assert storage._request_timeout is None


class TestValkeyCacheStorageContextManager:
    """Tests for context manager support."""

    def test_sync_context_manager(self, mock_client):
        """Test usage as a sync context manager."""
        mock_client.close = AsyncMock()
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            with ValkeyCacheStorage(host="localhost", port=6379) as storage:
                storage._client = mock_client
                assert storage is not None
            # After exiting, resources should be cleaned up
            assert storage._client is None

    def test_client_access_after_close_raises(self, mock_client):
        """Test that accessing client after close raises RuntimeError."""
        mock_client.close = AsyncMock()
        with patch.object(
            ValkeyCacheStorage, "_create_client", return_value=mock_client
        ):
            storage = ValkeyCacheStorage(host="localhost", port=6379)
            storage._client = mock_client
            storage.close()
            with pytest.raises(RuntimeError, match="has been closed"):
                _ = storage.client


class TestValkeyCacheStorageEventLoopSafety:
    """Tests for event loop safety in async client."""

    @pytest.mark.asyncio
    async def test_async_client_tracks_loop(self, valkey_cache, mock_client):
        """Test that _get_async_client tracks the current event loop."""
        valkey_cache._async_client = None
        mock_create = AsyncMock(return_value=mock_client)
        valkey_cache._create_client_async = mock_create

        client = await valkey_cache._get_async_client()
        assert client is mock_client
        assert valkey_cache._async_loop == asyncio.get_running_loop()
