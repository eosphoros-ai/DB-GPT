"""Base cache storage class."""

import logging
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import msgpack

from dbgpt.core.interface.cache import (
    CacheConfig,
    CacheKey,
    CachePolicy,
    CacheValue,
    K,
    RetrievalPolicy,
    V,
)
from dbgpt.util.memory_utils import _get_object_bytes

logger = logging.getLogger(__name__)


@dataclass
class StorageItem:
    """A class representing a storage item.

    This class encapsulates data related to a storage item, such as its length,
    the hash of the key, and the data for both the key and value.

    Parameters:
        length (int): The bytes length of the storage item.
        key_hash (bytes): The hash value of the storage item's key.
        key_data (bytes): The data of the storage item's key, represented in bytes.
        value_data (bytes): The data of the storage item's value, also in bytes.
    """

    length: int  # The bytes length of the storage item
    key_hash: bytes  # The hash value of the storage item's key
    key_data: bytes  # The data of the storage item's key
    value_data: bytes  # The data of the storage item's value

    @staticmethod
    def build_from(
        key_hash: bytes, key_data: bytes, value_data: bytes
    ) -> "StorageItem":
        """Build a StorageItem from the provided key and value data."""
        length = (
            32
            + _get_object_bytes(key_hash)
            + _get_object_bytes(key_data)
            + _get_object_bytes(value_data)
        )
        return StorageItem(
            length=length, key_hash=key_hash, key_data=key_data, value_data=value_data
        )

    @staticmethod
    def build_from_kv(key: CacheKey[K], value: CacheValue[V]) -> "StorageItem":
        """Build a StorageItem from the provided key and value."""
        key_hash = key.get_hash_bytes()
        key_data = key.serialize()
        value_data = value.serialize()
        return StorageItem.build_from(key_hash, key_data, value_data)

    def serialize(self) -> bytes:
        """Serialize the StorageItem into a byte stream using MessagePack.

        This method packs the object data into a dictionary, marking the
        key_data and value_data fields as raw binary data to avoid re-serialization.

        Returns:
            bytes: The serialized bytes.
        """
        obj = {
            "length": self.length,
            "key_hash": msgpack.ExtType(1, self.key_hash),
            "key_data": msgpack.ExtType(2, self.key_data),
            "value_data": msgpack.ExtType(3, self.value_data),
        }
        return msgpack.packb(obj)

    @staticmethod
    def deserialize(data: bytes) -> "StorageItem":
        """Deserialize bytes back into a StorageItem using MessagePack.

        This extracts the fields from the MessagePack dict back into
        a StorageItem object.

        Args:
            data (bytes): Serialized bytes

        Returns:
            StorageItem: Deserialized StorageItem object.
        """
        obj = msgpack.unpackb(data)
        key_hash = obj["key_hash"].data
        key_data = obj["key_data"].data
        value_data = obj["value_data"].data

        return StorageItem(
            length=obj["length"],
            key_hash=key_hash,
            key_data=key_data,
            value_data=value_data,
        )


class CacheStorage(ABC):
    """Base class for cache storage."""

    @abstractmethod
    def check_config(
        self,
        cache_config: Optional[CacheConfig] = None,
        raise_error: Optional[bool] = True,
    ) -> bool:
        """Check whether the CacheConfig is legal.

        Args:
            cache_config (Optional[CacheConfig]): Cache config.
            raise_error (Optional[bool]): Whether raise error if illegal.

        Returns:
            ValueError: Error when raise_error is True and config is illegal.
        """

    def support_async(self) -> bool:
        """Check whether the storage support async operation."""
        return False

    @abstractmethod
    def get(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[StorageItem]:
        """Retrieve a storage item from the cache using the provided key.

        Args:
            key (CacheKey[K]): The key to get cache
            cache_config (Optional[CacheConfig]): Cache config

        Returns:
            Optional[StorageItem]: The storage item retrieved according to key. If
                cache key not exist, return None.
        """

    async def aget(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[StorageItem]:
        """Retrieve a storage item from the cache using the provided key asynchronously.

        Args:
            key (CacheKey[K]): The key to get cache
            cache_config (Optional[CacheConfig]): Cache config

        Returns:
            Optional[StorageItem]: The storage item  of bytes retrieved according to
                key. If cache key not exist, return None.
        """
        raise NotImplementedError

    @abstractmethod
    def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Set a value in the cache for the provided key asynchronously.

        Args:
            key (CacheKey[K]): The key to set to cache
            value (CacheValue[V]): The value to set to cache
            cache_config (Optional[CacheConfig]): Cache config
        """

    async def aset(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Set a value in the cache for the provided key asynchronously.

        Args:
            key (CacheKey[K]): The key to set to cache
            value (CacheValue[V]): The value to set to cache
            cache_config (Optional[CacheConfig]): Cache config
        """
        raise NotImplementedError


class MemoryCacheStorage(CacheStorage):
    """A simple in-memory cache storage implementation."""

    def __init__(self, max_memory_mb: int = 256):
        """Create a new instance of MemoryCacheStorage."""
        self.cache: OrderedDict = OrderedDict()
        self.max_memory = max_memory_mb * 1024 * 1024
        self.current_memory_usage = 0

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
                    "MemoryCacheStorage only supports 'EXACT_MATCH' retrieval policy"
                )
            return False
        return True

    def get(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[StorageItem]:
        """Retrieve a storage item from the cache using the provided key."""
        self.check_config(cache_config, raise_error=True)
        # Exact match retrieval
        key_hash = hash(key)
        item: Optional[StorageItem] = self.cache.get(key_hash)
        logger.debug(f"MemoryCacheStorage get key {key}, hash {key_hash}, item: {item}")

        if not item:
            return None
        # Move the item to the end of the OrderedDict to signify recent use.
        self.cache.move_to_end(key_hash)
        return item

    def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Set a value in the cache for the provided key."""
        key_hash = hash(key)
        item = StorageItem.build_from_kv(key, value)
        # Calculate memory size of the new entry
        new_entry_size = _get_object_bytes(item)
        # Evict entries if necessary
        while self.current_memory_usage + new_entry_size > self.max_memory:
            self._apply_cache_policy(cache_config)

        # Store the item in the cache.
        self.cache[key_hash] = item
        self.current_memory_usage += new_entry_size
        logger.debug(f"MemoryCacheStorage set key {key}, hash {key_hash}, item: {item}")

    def exists(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> bool:
        """Check if the key exists in the cache."""
        return self.get(key, cache_config) is not None

    def _apply_cache_policy(self, cache_config: Optional[CacheConfig] = None):
        # Remove the oldest/newest item based on the cache policy.
        if cache_config and cache_config.cache_policy == CachePolicy.FIFO:
            self.cache.popitem(last=False)
        else:  # Default is LRU
            self.cache.popitem(last=True)
