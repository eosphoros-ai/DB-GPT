"""DB-GPT: Next Generation Data Interaction Solution with LLMs.
"""
from dbgpt import _version  # noqa: E402
from dbgpt.component import BaseComponent, SystemApp  # noqa: F401

_CORE_LIBS = ["core", "rag", "model", "agent", "datasource", "vis", "storage", "train"]
_SERVE_LIBS = ["serve"]
_LIBS = _CORE_LIBS + _SERVE_LIBS


__version__ = _version.version

__ALL__ = ["__version__", "SystemApp", "BaseComponent"]


def __getattr__(name: str):
    # Lazy load
    import importlib

    if name in _LIBS:
        return importlib.import_module("." + name, __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
