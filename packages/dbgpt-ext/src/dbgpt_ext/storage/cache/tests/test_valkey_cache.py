"""Unit tests for ValkeyCacheStorage.

These tests use mocked valkey-glide client and do not require a running Valkey server.
"""

from __future__ import annotations

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
