"""Disk storage for cache.

Implement the cache storage using rocksdb.
"""

import logging
from typing import Optional

from rocksdict import Options, Rdict

from dbgpt.core.interface.cache import (
    CacheConfig,
    CacheKey,
    CacheValue,
    K,
    RetrievalPolicy,
    V,
)

from ..base import CacheStorage, StorageItem

logger = logging.getLogger(__name__)


def db_options(mem_table_buffer_mb: int = 256, background_threads: int = 2):
    """Create rocksdb options."""
    opt = Options()
    # create table
    opt.create_if_missing(True)
    # config to more jobs, default 2
    opt.set_max_background_jobs(background_threads)
    # configure mem-table to a large value
    opt.set_write_buffer_size(mem_table_buffer_mb * 1024 * 1024)
    # opt.set_write_buffer_size(1024)
    # opt.set_level_zero_file_num_compaction_trigger(4)
    # configure l0 and l1 size, let them have the same size (1 GB)
    # opt.set_max_bytes_for_level_base(0x40000000)
    # 256 MB file size
    # opt.set_target_file_size_base(0x10000000)
    # use a smaller compaction multiplier
    # opt.set_max_bytes_for_level_multiplier(4.0)
    # use 8-byte prefix (2 ^ 64 is far enough for transaction counts)
    # opt.set_prefix_extractor(SliceTransform.create_max_len_prefix(8))
    # set to plain-table
    # opt.set_plain_table_factory(PlainTableFactoryOptions())
    return opt


class DiskCacheStorage(CacheStorage):
    """Disk cache storage using rocksdb."""

    def __init__(self, persist_dir: str, mem_table_buffer_mb: int = 256) -> None:
        """Create a new instance of DiskCacheStorage."""
        super().__init__()
        self.db: Rdict = Rdict(
            persist_dir, db_options(mem_table_buffer_mb=mem_table_buffer_mb)
        )

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
                    "DiskCacheStorage only supports 'EXACT_MATCH' retrieval policy"
                )
            return False
        return True

    def get(
        self, key: CacheKey[K], cache_config: Optional[CacheConfig] = None
    ) -> Optional[StorageItem]:
        """Retrieve a storage item from the cache using the provided key."""
        self.check_config(cache_config, raise_error=True)

        # Exact match retrieval
        key_hash = key.get_hash_bytes()
        item_bytes = self.db.get(key_hash)
        if not item_bytes:
            return None
        item = StorageItem.deserialize(item_bytes)
        logger.debug(f"Read file cache, key: {key}, storage item: {item}")
        return item

    def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Set a value in the cache for the provided key."""
        item = StorageItem.build_from_kv(key, value)
        key_hash = item.key_hash
        self.db[key_hash] = item.serialize()
        logger.debug(f"Save file cache, key: {key}, value: {value}")
