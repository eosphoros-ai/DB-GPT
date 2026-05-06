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
        db: int = 0,
        use_ssl: bool = False,
        key_prefix: str = "dbgpt_cache:",
        ttl_seconds: Optional[int] = None,
    ):
        """Initialize ValkeyCacheStorage.

        Args:
            host: Valkey server host. Defaults to VALKEY_HOST env or localhost.
            port: Valkey server port. Defaults to VALKEY_PORT env or 6379.
            password: Valkey password. Defaults to VALKEY_PASSWORD env.
            db: Valkey database number.
            use_ssl: Whether to use TLS.
            key_prefix: Prefix for all cache keys.
            ttl_seconds: Optional TTL in seconds for cache entries.
                If None, entries don't expire.
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
        self._db = db
        self._use_ssl = use_ssl
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._client = None
        self._loop = asyncio.new_event_loop()

    @property
    def client(self):
        """Get or create the Valkey client (lazy initialization)."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        """Create a Valkey-glide client."""
        from glide import GlideClient, GlideClientConfiguration, NodeAddress

        node = NodeAddress(host=self._host, port=self._port)

        if self._password:
            from glide import ServerCredentials

            client_config = GlideClientConfiguration(
                addresses=[node],
                use_tls=self._use_ssl,
                credentials=ServerCredentials(password=self._password),
            )
        else:
            client_config = GlideClientConfiguration(
                addresses=[node],
                use_tls=self._use_ssl,
            )

        return self._loop.run_until_complete(GlideClient.create(client_config))

    def _run_async(self, coro):
        """Run an async coroutine synchronously using the dedicated event loop."""
        return self._loop.run_until_complete(coro)

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
            logger.warning(f"Failed to deserialize cache item: {e}")
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

        data = await self.client.get(valkey_key)
        if data is None:
            return None

        if isinstance(data, str):
            data = data.encode()

        try:
            return StorageItem.deserialize(data)
        except Exception as e:
            logger.warning(f"Failed to deserialize cache item: {e}")
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

        if self._ttl_seconds:
            from glide import ExpirySet, ExpiryType

            expiry = ExpirySet(ExpiryType.SEC, self._ttl_seconds)
            self._run_async(self.client.set(valkey_key, data, expiry=expiry))
        else:
            self._run_async(self.client.set(valkey_key, data))

        logger.debug(f"ValkeyCacheStorage set key hash={valkey_key}")

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

        if self._ttl_seconds:
            from glide import ExpirySet, ExpiryType

            expiry = ExpirySet(ExpiryType.SEC, self._ttl_seconds)
            await self.client.set(valkey_key, data, expiry=expiry)
        else:
            await self.client.set(valkey_key, data)

        logger.debug(f"ValkeyCacheStorage aset key hash={valkey_key}")

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
