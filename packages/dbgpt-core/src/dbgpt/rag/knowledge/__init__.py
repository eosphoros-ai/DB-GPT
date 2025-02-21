"""Module Of Knowledge."""

from typing import Any, Dict

_MODULE_CACHE: Dict[str, Any] = {}


def __getattr__(name: str):
    # Lazy load
    import importlib

    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]

    _LIBS = {
        "Knowledge": "base",
        "KnowledgeType": "base",
        "ChunkStrategy": "base",
    }

    if name in _LIBS:
        module_path = "." + _LIBS[name]
        module = importlib.import_module(module_path, __name__)
        attr = getattr(module, name)
        _MODULE_CACHE[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Knowledge",
    "KnowledgeType",
    "ChunkStrategy",
]
