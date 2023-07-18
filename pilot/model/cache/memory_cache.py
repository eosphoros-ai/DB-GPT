from typing import Dict, Any
from pilot.model.cache import Cache


class InMemoryCache(Cache):
    def __init__(self) -> None:
        "Initialize that stores things in memory."
        self._cache: Dict[str, Any] = {}

    def create(self, key: str) -> bool:
        pass

    def clear(self):
        return self._cache.clear()

    def __setitem__(self, key: str, value: str) -> None:
        self._cache[key] = value

    def __getitem__(self, key: str) -> str:
        return self._cache[key]

    def __contains__(self, key: str) -> bool:
        return self._cache.get(key, None) is not None
