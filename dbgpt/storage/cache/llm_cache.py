"""Cache client for LLM."""

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union, cast

from dbgpt.core import ModelOutput
from dbgpt.core.interface.cache import CacheClient, CacheConfig, CacheKey, CacheValue

from .manager import CacheManager


@dataclass
class LLMCacheKeyData:
    """Cache key data for LLM."""

    prompt: str
    model_name: str
    temperature: Optional[float] = 0.7
    max_new_tokens: Optional[int] = None
    top_p: Optional[float] = 1.0
    # See dbgpt.model.base.ModelType
    model_type: Optional[str] = "huggingface"


CacheOutputType = Union[ModelOutput, List[ModelOutput]]


@dataclass
class LLMCacheValueData:
    """Cache value data for LLM."""

    output: CacheOutputType
    user: Optional[str] = None
    _is_list: bool = False

    @staticmethod
    def from_dict(**kwargs) -> "LLMCacheValueData":
        """Create LLMCacheValueData object from dict."""
        output = kwargs.get("output")
        if not output:
            raise ValueError("Can't new LLMCacheValueData object, output is None")
        if isinstance(output, dict):
            output = ModelOutput(**output)
        elif isinstance(output, list):
            kwargs["_is_list"] = True
            output_list = []
            for out in output:
                if isinstance(out, dict):
                    out = ModelOutput(**out)
                output_list.append(out)
            output = output_list
        kwargs["output"] = output
        return LLMCacheValueData(**kwargs)

    def to_dict(self) -> Dict:
        """Convert to dict."""
        output = self.output
        is_list = False
        if isinstance(output, list):
            output_list = []
            is_list = True
            for out in output:
                output_list.append(out.to_dict())
            output = output_list  # type: ignore
        else:
            output = output.to_dict()  # type: ignore
        return {"output": output, "_is_list": is_list, "user": self.user}

    @property
    def is_list(self) -> bool:
        """Return whether the output is a list."""
        return self._is_list

    def __str__(self) -> str:
        """Return string representation."""
        if not isinstance(self.output, list):
            return f"user: {self.user}, output: {self.output}"
        else:
            return f"user: {self.user}, output(last two item): {self.output[-2:]}"


class LLMCacheKey(CacheKey[LLMCacheKeyData]):
    """Cache key for LLM."""

    def __init__(self, **kwargs) -> None:
        """Create a new instance of LLMCacheKey."""
        super().__init__()
        self.config = LLMCacheKeyData(**kwargs)

    def __hash__(self) -> int:
        """Return the hash value of the object."""
        serialize_bytes = self.serialize()
        return int(hashlib.sha256(serialize_bytes).hexdigest(), 16)

    def __eq__(self, other: Any) -> bool:
        """Check equality with another key."""
        if not isinstance(other, LLMCacheKey):
            return False
        return self.config == other.config

    def get_hash_bytes(self) -> bytes:
        """Return the byte array of hash value.

        Returns:
            bytes: The byte array of hash value.
        """
        serialize_bytes = self.serialize()
        return hashlib.sha256(serialize_bytes).digest()

    def to_dict(self) -> Dict:
        """Convert to dict."""
        return asdict(self.config)

    def get_value(self) -> LLMCacheKeyData:
        """Return the real object of current cache key."""
        return self.config


class LLMCacheValue(CacheValue[LLMCacheValueData]):
    """Cache value for LLM."""

    def __init__(self, **kwargs) -> None:
        """Create a new instance of LLMCacheValue."""
        super().__init__()
        self.value = LLMCacheValueData.from_dict(**kwargs)

    def to_dict(self) -> Dict:
        """Convert to dict."""
        return self.value.to_dict()

    def get_value(self) -> LLMCacheValueData:
        """Return the underlying real value."""
        return self.value

    def __str__(self) -> str:
        """Return string representation."""
        return f"value: {str(self.value)}"


class LLMCacheClient(CacheClient[LLMCacheKeyData, LLMCacheValueData]):
    """Cache client for LLM."""

    def __init__(self, cache_manager: CacheManager) -> None:
        """Create a new instance of LLMCacheClient."""
        super().__init__()
        self._cache_manager: CacheManager = cache_manager

    async def get(
        self,
        key: LLMCacheKey,  # type: ignore
        cache_config: Optional[CacheConfig] = None,
    ) -> Optional[LLMCacheValue]:
        """Retrieve a value from the cache using the provided key.

        Args:
            key (LLMCacheKey): The key to get cache
            cache_config (Optional[CacheConfig]): Cache config

        Returns:
            Optional[LLMCacheValue]: The value retrieved according to key. If cache key
                not exist, return None.
        """
        return cast(
            LLMCacheValue,
            await self._cache_manager.get(key, LLMCacheValue, cache_config),
        )

    async def set(
        self,
        key: LLMCacheKey,  # type: ignore
        value: LLMCacheValue,  # type: ignore
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        """Set a value in the cache for the provided key."""
        return await self._cache_manager.set(key, value, cache_config)

    async def exists(
        self,
        key: LLMCacheKey,  # type: ignore
        cache_config: Optional[CacheConfig] = None,
    ) -> bool:
        """Check if a key exists in the cache."""
        return await self.get(key, cache_config) is not None

    def new_key(self, **kwargs) -> LLMCacheKey:  # type: ignore
        """Create a cache key with params."""
        key = LLMCacheKey(**kwargs)
        key.set_serializer(self._cache_manager.serializer)
        return key

    def new_value(self, **kwargs) -> LLMCacheValue:  # type: ignore
        """Create a cache value with params."""
        value = LLMCacheValue(**kwargs)
        value.set_serializer(self._cache_manager.serializer)
        return value
