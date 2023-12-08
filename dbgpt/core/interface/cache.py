from abc import ABC, abstractmethod

from typing import Any, TypeVar, Generic, Optional
from dataclasses import dataclass
from enum import Enum

from dbgpt.core.interface.serialization import Serializable

K = TypeVar("K")
V = TypeVar("V")


class RetrievalPolicy(str, Enum):
    EXACT_MATCH = "exact_match"
    SIMILARITY_MATCH = "similarity_match"


class CachePolicy(str, Enum):
    LRU = "lru"
    FIFO = "fifo"


@dataclass
class CacheConfig:
    retrieval_policy: Optional[RetrievalPolicy] = RetrievalPolicy.EXACT_MATCH
    cache_policy: Optional[CachePolicy] = CachePolicy.LRU


class CacheKey(Serializable, ABC, Generic[K]):
    """The key of the cache. Must be hashable and comparable.

    Supported cache keys:
    - The LLM cache key: Include user prompt and the parameters to LLM.
    - The embedding model cache key: Include the texts to embedding and the parameters to embedding model.
    """

    @abstractmethod
    def __hash__(self) -> int:
        """Return the hash value of the key."""

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        """Check equality with another key."""

    @abstractmethod
    def get_hash_bytes(self) -> bytes:
        """Return the byte array of hash value."""

    @abstractmethod
    def get_value(self) -> K:
        """Get the underlying value of the cache key.

        Returns:
            K: The real object of current cache key
        """


class CacheValue(Serializable, ABC, Generic[V]):
    """Cache value abstract class."""

    @abstractmethod
    def get_value(self) -> V:
        """Get the underlying real value."""


class CacheClient(ABC, Generic[K, V]):
    """The cache client interface."""

    @abstractmethod
    async def get(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[CacheValue[V]]:
        """Retrieve a value from the cache using the provided key.

        Args:
            key (CacheKey[K]): The key to get cache
            cache_config (Optional[CacheConfig]): Cache config

        Returns:
            Optional[CacheValue[V]]: The value retrieved according to key. If cache key not exist, return None.
        """

    @abstractmethod
    async def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Set a value in the cache for the provided key.

        Args:
            key (CacheKey[K]): The key to set to cache
            value (CacheValue[V]): The value to set to cache
            cache_config (Optional[CacheConfig]): Cache config
        """

    @abstractmethod
    async def exists(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> bool:
        """Check if a key exists in the cache.

        Args:
            key (CacheKey[K]): The key to set to cache
            cache_config (Optional[CacheConfig]): Cache config

        Return:
            bool: True if the key in the cache, otherwise is False
        """

    @abstractmethod
    def new_key(self, **kwargs) -> CacheKey[K]:
        """Create a cache key with params"""

    @abstractmethod
    def new_value(self, **kwargs) -> CacheValue[K]:
        """Create a cache key with params"""
