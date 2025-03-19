"""Cache manager."""

import logging
from abc import ABC, abstractmethod
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Optional, Type, cast

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core import CacheConfig, CacheKey, CacheValue, Serializable, Serializer
from dbgpt.core.interface.cache import K, V
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import BaseParameters

from .storage.base import CacheStorage

logger = logging.getLogger(__name__)


@dataclass
class ModelCacheParameters(BaseParameters):
    """Model cache configuration."""

    __cfg_type__ = "utils"

    enable_model_cache: bool = field(
        default=True,
        metadata={
            "help": _("Whether to enable model cache, default is True"),
        },
    )
    storage_type: str = field(
        default="memory",
        metadata={
            "help": _("The storage type, default is memory"),
        },
    )
    max_memory_mb: int = field(
        default=256,
        metadata={
            "help": _("The max memory in MB, default is 256"),
        },
    )
    persist_dir: str = field(
        default="model_cache",
        metadata={
            "help": _("The persist directory, default is model_cache"),
        },
    )


class CacheManager(BaseComponent, ABC):
    """The cache manager interface."""

    name = ComponentType.MODEL_CACHE_MANAGER

    def __init__(self, system_app: SystemApp | None = None):
        """Create cache manager."""
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Initialize cache manager."""
        self.system_app = system_app

    @abstractmethod
    async def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ):
        """Set cache with key."""

    @abstractmethod
    async def get(
        self,
        key: CacheKey[K],
        cls: Type[Serializable],
        cache_config: Optional[CacheConfig] = None,
    ) -> Optional[CacheValue[V]]:
        """Retrieve cache with key."""

    @property
    @abstractmethod
    def serializer(self) -> Serializer:
        """Return serializer to serialize/deserialize cache value."""


class LocalCacheManager(CacheManager):
    """Local cache manager."""

    def __init__(
        self, system_app: SystemApp, serializer: Serializer, storage: CacheStorage
    ) -> None:
        """Create local cache manager."""
        super().__init__(system_app)
        self._serializer = serializer
        self._storage = storage

    @property
    def executor(self) -> Executor:
        """Return executor."""
        return self.system_app.get_component(  # type: ignore
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

    async def set(
        self,
        key: CacheKey[K],
        value: CacheValue[V],
        cache_config: Optional[CacheConfig] = None,
    ):
        """Set cache with key."""
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
    ) -> Optional[CacheValue[V]]:
        """Retrieve cache with key."""
        if self._storage.support_async():
            item_bytes = await self._storage.aget(key, cache_config)
        else:
            item_bytes = await blocking_func_to_async(
                self.executor, self._storage.get, key, cache_config
            )
        if not item_bytes:
            return None
        return cast(
            CacheValue[V], self._serializer.deserialize(item_bytes.value_data, cls)
        )

    @property
    def serializer(self) -> Serializer:
        """Return serializer to serialize/deserialize cache value."""
        return self._serializer


def initialize_cache(
    system_app: SystemApp, storage_type: str, max_memory_mb: int, persist_dir: str
):
    """Initialize cache manager.

    Args:
        system_app (SystemApp): The system app.
        storage_type (str): The storage type.
        max_memory_mb (int): The max memory in MB.
        persist_dir (str): The persist directory.
    """
    from dbgpt.util.serialization.json_serialization import JsonSerializer

    from .storage.base import MemoryCacheStorage

    if storage_type == "disk":
        try:
            from .storage.disk.disk_storage import DiskCacheStorage

            cache_storage: CacheStorage = DiskCacheStorage(
                persist_dir, mem_table_buffer_mb=max_memory_mb
            )
        except ImportError as e:
            logger.warn(
                f"Can't import DiskCacheStorage, use MemoryCacheStorage, import error "
                f"message: {str(e)}"
            )
            cache_storage = MemoryCacheStorage(max_memory_mb=max_memory_mb)
    else:
        cache_storage = MemoryCacheStorage(max_memory_mb=max_memory_mb)
    system_app.register(
        LocalCacheManager, serializer=JsonSerializer(), storage=cache_storage
    )
