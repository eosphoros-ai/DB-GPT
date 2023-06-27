import os
import diskcache
import platformdirs
from pilot.model.cache import Cache


class DiskCache(Cache):
    """DiskCache is a cache that uses diskcache lib.
    https://github.com/grantjenks/python-diskcache
    """

    def __init__(self, llm_name: str):
        self._diskcache = diskcache.Cache(
            os.path.join(platformdirs.user_cache_dir("dbgpt"), f"_{llm_name}.diskcache")
        )

    def __getitem__(self, key: str) -> str:
        return self._diskcache[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._diskcache[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._diskcache

    def clear(self):
        self._diskcache.clear()
