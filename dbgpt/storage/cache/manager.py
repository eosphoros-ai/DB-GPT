from abc import ABC, abstractmethod
from typing import Optional, Type
import logging
from concurrent.futures import Executor
from dbgpt.storage.cache.storage.base import CacheStorage
from dbgpt.core.interface.cache import K, V
from dbgpt.core import (
    CacheKey,
    CacheValue,
    CacheConfig,
    Serializer,
    Serializable,
)
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async

logger = logging.getLogger(__name__)


class CacheManager(BaseComponent, ABC):
    name = ComponentType.MODEL_CACHE_MANAGER

    def __init__(self, system_app: SystemApp | None = None):
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        self.system_app = system_app

    @abstractmethod
    async def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ):
        """Set cache"""

    @abstractmethod
    async def get(
        self,
        key: CacheKey[K],
        cls: Type[Serializable],
        cache_config: Optional[CacheConfig] = None,
    ) -> CacheValue[V]:
        """Get cache with key"""

    @property
    @abstractmethod
    def serializer(self) -> Serializer:
        """Get cache serializer"""


class LocalCacheManager(CacheManager):
    def __init__(
        self, system_app: SystemApp, serializer: Serializer, storage: CacheStorage
    ) -> None:
        super().__init__(system_app)
        self._serializer = serializer
        self._storage = storage

    @property
    def executor(self) -> Executor:
        """Return executor to submit task"""
        self._executor = self.system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

    async def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ):
        if self._storage.support_async():
            await self._storage.aset(key, value, cache_config)
        else:
            await blocking_func_to_async(
                self.executor, self._storage.set, key, value, cache_config
            )

    async def get(
        self,
        key: CacheKey[K],
        cls: Type[Serializable],
        cache_config: Optional[CacheConfig] = None,
    ) -> CacheValue[V]:
        if self._storage.support_async():
            item_bytes = await self._storage.aget(key, cache_config)
        else:
            item_bytes = await blocking_func_to_async(
                self.executor, self._storage.get, key, cache_config
            )
        if not item_bytes:
            return None
        return self._serializer.deserialize(item_bytes.value_data, cls)

    @property
    def serializer(self) -> Serializer:
        return self._serializer


def initialize_cache(
    system_app: SystemApp, storage_type: str, max_memory_mb: int, persist_dir: str
):
    from dbgpt.util.serialization.json_serialization import JsonSerializer
    from dbgpt.storage.cache.storage.base import MemoryCacheStorage

    cache_storage = None
    if storage_type == "disk":
        try:
            from dbgpt.storage.cache.storage.disk.disk_storage import DiskCacheStorage

            cache_storage = DiskCacheStorage(
                persist_dir, mem_table_buffer_mb=max_memory_mb
            )
        except ImportError as e:
            logger.warn(
                f"Can't import DiskCacheStorage, use MemoryCacheStorage, import error message: {str(e)}"
            )
            cache_storage = MemoryCacheStorage(max_memory_mb=max_memory_mb)
    else:
        cache_storage = MemoryCacheStorage(max_memory_mb=max_memory_mb)
    system_app.register(
        LocalCacheManager, serializer=JsonSerializer(), storage=cache_storage
    )
