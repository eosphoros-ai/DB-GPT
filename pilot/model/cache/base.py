import json
import hashlib
from typing import Any, Dict
from abc import ABC, abstractmethod


class Cache(ABC):
    def create(self, key: str) -> bool:
        pass

    def clear(self):
        pass

    @abstractmethod
    def __getitem__(self, key: str) -> str:
        """get an item from the cache or throw key error"""
        pass

    @abstractmethod
    def __setitem__(self, key: str, value: str) -> None:
        """set an item in the cache"""
        pass

    @abstractmethod
    def __contains__(self, key: str) -> bool:
        """see if we can return a cached value for the passed key"""
        pass
