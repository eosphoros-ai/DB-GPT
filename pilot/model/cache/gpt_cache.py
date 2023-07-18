import os
from typing import Dict, Any
import platformdirs

from pilot.model.cache import Cache

try:
    from gptcache.adapter.api import get, put, init_similar_cache
except ImportError:
    pass


class GPTCache(Cache):

    """
    GPTCache is a semantic cache that uses
    """

    def __init__(self, cache) -> None:
        """GPT Cache is a semantic cache that uses GPTCache lib."""

        if isinstance(cache, str):
            _cache = Cache()
            init_similar_cache(
                data_dir=os.path.join(
                    platformdirs.user_cache_dir("dbgpt"), f"_{cache}.gptcache"
                ),
                cache_obj=_cache,
            )
        else:
            _cache = cache

        self._cache_obj = _cache

    def __getitem__(self, key: str) -> str:
        return get(key)

    def __setitem__(self, key: str, value: str) -> None:
        put(key, value)

    def __contains__(self, key: str) -> bool:
        return get(key) is not None

    def create(self, llm: str, **kwargs: Dict[str, Any]) -> str:
        pass
