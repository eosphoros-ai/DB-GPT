from typing import Optional, Dict, Any, Union, List
from dataclasses import dataclass, asdict
import hashlib

from dbgpt.core.interface.cache import (
    CacheKey,
    CacheValue,
    CacheClient,
    CacheConfig,
)
from dbgpt.storage.cache.manager import CacheManager
from dbgpt.core import ModelOutput, Serializer
from dbgpt.model.base import ModelType


@dataclass
class LLMCacheKeyData:
    prompt: str
    model_name: str
    temperature: Optional[float] = 0.7
    max_new_tokens: Optional[int] = None
    top_p: Optional[float] = 1.0
    model_type: Optional[str] = ModelType.HF


CacheOutputType = Union[ModelOutput, List[ModelOutput]]


@dataclass
class LLMCacheValueData:
    output: CacheOutputType
    user: Optional[str] = None
    _is_list: Optional[bool] = False

    @staticmethod
    def from_dict(**kwargs) -> "LLMCacheValueData":
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
        output = self.output
        is_list = False
        if isinstance(output, list):
            output_list = []
            is_list = True
            for out in output:
                output_list.append(out.to_dict())
            output = output_list
        else:
            output = output.to_dict()
        return {"output": output, "_is_list": is_list, "user": self.user}

    @property
    def is_list(self) -> bool:
        return self._is_list

    def __str__(self) -> str:
        if not isinstance(self.output, list):
            return f"user: {self.user}, output: {self.output}"
        else:
            return f"user: {self.user}, output(last two item): {self.output[-2:]}"


class LLMCacheKey(CacheKey[LLMCacheKeyData]):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.config = LLMCacheKeyData(**kwargs)

    def __hash__(self) -> int:
        serialize_bytes = self.serialize()
        return int(hashlib.sha256(serialize_bytes).hexdigest(), 16)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LLMCacheKey):
            return False
        return self.config == other.config

    def get_hash_bytes(self) -> bytes:
        serialize_bytes = self.serialize()
        return hashlib.sha256(serialize_bytes).digest()

    def to_dict(self) -> Dict:
        return asdict(self.config)

    def get_value(self) -> LLMCacheKeyData:
        return self.config


class LLMCacheValue(CacheValue[LLMCacheValueData]):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.value = LLMCacheValueData.from_dict(**kwargs)

    def to_dict(self) -> Dict:
        return self.value.to_dict()

    def get_value(self) -> LLMCacheValueData:
        return self.value

    def __str__(self) -> str:
        return f"value: {str(self.value)}"


class LLMCacheClient(CacheClient[LLMCacheKeyData, LLMCacheValueData]):
    def __init__(self, cache_manager: CacheManager) -> None:
        super().__init__()
        self._cache_manager: CacheManager = cache_manager

    async def get(
        self, key: LLMCacheKey, cache_config: Optional[CacheConfig] = None
    ) -> Optional[LLMCacheValue]:
        return await self._cache_manager.get(key, LLMCacheValue, cache_config)

    async def set(
        self,
        key: LLMCacheKey,
        value: LLMCacheValue,
        cache_config: Optional[CacheConfig] = None,
    ) -> None:
        return await self._cache_manager.set(key, value, cache_config)

    async def exists(
        self, key: LLMCacheKey, cache_config: Optional[CacheConfig] = None
    ) -> bool:
        return await self.get(key, cache_config) is not None

    def new_key(self, **kwargs) -> LLMCacheKey:
        key = LLMCacheKey(**kwargs)
        key.set_serializer(self._cache_manager.serializer)
        return key

    def new_value(self, **kwargs) -> LLMCacheValue:
        value = LLMCacheValue(**kwargs)
        value.set_serializer(self._cache_manager.serializer)
        return value
