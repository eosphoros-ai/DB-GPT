"""Valkey cache storage implementation.

Uses valkey-glide client for high-performance in-memory caching of LLM
responses and embeddings.
"""

import asyncio
import logging
import os
from typing import Optional

from dbgpt.core.interface.cache import (
    CacheConfig,
    CacheKey,
    CacheValue,
    K,
    RetrievalPolicy,
    V,
)
from dbgpt.storage.cache.storage.base import CacheStorage, StorageItem

logger = logging.getLogger(__name__)


class ValkeyCacheStorage(CacheStorage):
    """Valkey-based cache storage using valkey-glide client.

    Stores serialized cache items as binary values in Valkey with optional TTL.
    Supports both sync and async operations.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        use_ssl: bool = False,
        key_prefix: str = "dbgpt_cache:",
        ttl_seconds: Optional[int] = None,
        request_timeout: Optional[int] = 5000,
    ):
        """Initialize ValkeyCacheStorage.

        Args:
            host: Valkey server host. Defaults to VALKEY_HOST env or localhost.
            port: Valkey server port. Defaults to VALKEY_PORT env or 6379.
            password: Valkey password. Defaults to VALKEY_PASSWORD env.
            use_ssl: Whether to use TLS.
            key_prefix: Prefix for all cache keys.
            ttl_seconds: Optional TTL in seconds for cache entries.
                If None, entries don't expire.
            request_timeout: Request timeout in milliseconds. Defaults to 5000ms.
                If None, no timeout is set.
        """
        try:
            import glide  # noqa: F401
        except ImportError:
            raise ImportError(
                "Please install valkey-glide: pip install 'valkey-glide>=2.3.0'"
            )

        self._host = host or os.getenv("VALKEY_HOST", "localhost")
        self._port = port or int(os.getenv("VALKEY_PORT", "6379"))
        self._password = password or os.getenv("VALKEY_PASSWORD")
        self._use_ssl = use_ssl
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._request_timeout = request_timeout
        self._client = None
        self._async_client = None
        self._async_loop = None
        self._loop = asyncio.new_event_loop()

    @property
    def client(self):
        """Get or create the Valkey client for sync operations (lazy initialization)."""
        if self._loop.is_closed():
            raise RuntimeError("ValkeyCacheStorage has been closed")
        if self._client is None:
            self._client = self._loop.run_until_complete(self._create_client_async())
        return self._client

    def _get_client_config(self):
        """Build the GlideClientConfiguration."""
        from glide import GlideClientConfiguration, NodeAddress

        node = NodeAddress(host=self._host, port=self._port)

        kwargs = {
            "addresses": [node],
            "use_tls": self._use_ssl,
        }
        if self._request_timeout is not None:
            kwargs["request_timeout"] = self._request_timeout

        if self._password:
            from glide import ServerCredentials

            kwargs["credentials"] = ServerCredentials(password=self._password)

        return GlideClientConfiguration(**kwargs)

    async def _create_client_async(self):
        """Create a Valkey-glide client on the current event loop."""
        from glide import GlideClient

        return await GlideClient.create(self._get_client_config())

    def _create_client(self):
        """Create a Valkey-glide client (sync helper, used by tests)."""
        return self._loop.run_until_complete(self._create_client_async())

    async def _get_async_client(self):
        """Get or create a client bound to the current running event loop.

        If called from a different event loop than self._loop, creates a fresh
        client on the current loop to avoid cross-loop issues.
        """
        current_loop = asyncio.get_running_loop()
        if self._async_client is None or self._async_loop != current_loop:
            if self._async_client is not None:
                try:
                    await self._async_client.close()
                except Exception:
                    pass
            self._async_client = await self._create_client_async()
            self._async_loop = current_loop
        return self._async_client

    def _run_async(self, coro):
        """Run an async coroutine synchronously using the dedicated event loop."""
        return self._loop.run_until_complete(coro)

    def close(self):
        """Close the client connection and event loop."""
        if self._client is not None:
            try:
                self._loop.run_until_complete(self._client.close())
            except Exception:
                pass
            self._client = None
        if self._async_client is not None:
            try:
                self._loop.run_until_complete(self._async_client.close())
            except Exception:
                pass
            self._async_client = None
        if self._loop and not self._loop.is_closed():
            self._loop.close()

    def __enter__(self):
        """Support usage as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close resources on context manager exit."""
        self.close()
        return False

    async def __aenter__(self):
        """Support usage as an async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close resources on async context manager exit."""
        if self._async_client is not None:
            try:
                await self._async_client.close()
            except Exception:
                pass
            self._async_client = None
        self.close()
        return False

    def _make_key(self, key: CacheKey[K]) -> str:
        """Build the full Valkey key from a CacheKey."""
        key_hash = key.get_hash_bytes()
        return self._key_prefix + key_hash.hex()

    def check_config(
        self,
        cache_config: Optional[CacheConfig] = None,
        raise_error: Optional[bool] = True,
    ) -> bool:
        """Check whether the CacheConfig is legal."""
        if (
            cache_config
            and cache_config.retrieval_policy != RetrievalPolicy.EXACT_MATCH
        ):
            if raise_error:
                raise ValueError(
                    "ValkeyCacheStorage only supports 'EXACT_MATCH' retrieval policy"
                )
            return False
        return True

    def support_async(self) -> bool:
        """Valkey supports async operations."""
        return True

    def get(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[StorageItem]:
        """Retrieve a storage item from Valkey.

        Args:
            key: The cache key.
            cache_config: Optional cache configuration.

        Returns:
            The StorageItem if found, None otherwise.
        """
        self.check_config(cache_config, raise_error=True)
        valkey_key = self._make_key(key)

        data = self._run_async(self.client.get(valkey_key))
        if data is None:
            return None

        if isinstance(data, str):
            data = data.encode()

        try:
            return StorageItem.deserialize(data)
        except Exception as e:
            logger.warning("Failed to deserialize cache item: %s", e)
            return None

    async def aget(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[StorageItem]:
        """Retrieve a storage item from Valkey asynchronously.

        Args:
            key: The cache key.
            cache_config: Optional cache configuration.

        Returns:
            The StorageItem if found, None otherwise.
        """
        self.check_config(cache_config, raise_error=True)
        valkey_key = self._make_key(key)

        client = await self._get_async_client()
        data = await client.get(valkey_key)
        if data is None:
            return None

        if isinstance(data, str):
            data = data.encode()

        try:
            return StorageItem.deserialize(data)
        except Exception as e:
            logger.warning("Failed to deserialize cache item: %s", e)
            return None

    def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Store a cache item in Valkey.

        Args:
            key: The cache key.
            value: The cache value.
            cache_config: Optional cache configuration.
        """
        valkey_key = self._make_key(key)
        item = StorageItem.build_from_kv(key, value)
        data = item.serialize()

        if self._ttl_seconds is not None:
            from glide import ExpirySet, ExpiryType

            expiry = ExpirySet(ExpiryType.SEC, self._ttl_seconds)
            self._run_async(self.client.set(valkey_key, data, expiry=expiry))
        else:
            self._run_async(self.client.set(valkey_key, data))

        logger.debug("ValkeyCacheStorage set key hash=%s", valkey_key)

    async def aset(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Store a cache item in Valkey asynchronously.

        Args:
            key: The cache key.
            value: The cache value.
            cache_config: Optional cache configuration.
        """
        valkey_key = self._make_key(key)
        item = StorageItem.build_from_kv(key, value)
        data = item.serialize()

        client = await self._get_async_client()
        if self._ttl_seconds is not None:
            from glide import ExpirySet, ExpiryType

            expiry = ExpirySet(ExpiryType.SEC, self._ttl_seconds)
            await client.set(valkey_key, data, expiry=expiry)
        else:
            await client.set(valkey_key, data)

        logger.debug("ValkeyCacheStorage aset key hash=%s", valkey_key)

    def exists(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key.
            cache_config: Optional cache configuration.

        Returns:
            True if the key exists.
        """
        valkey_key = self._make_key(key)
        result = self._run_async(self.client.exists([valkey_key]))
        return result > 0
