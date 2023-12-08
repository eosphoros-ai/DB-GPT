from dbgpt.component import SystemApp, BaseComponent


__ALL__ = ["SystemApp", "BaseComponent"]

_CORE_LIBS = ["core", "rag", "model", "agent", "datasource", "vis", "storage", "train"]
_SERVE_LIBS = ["serve"]
_LIBS = _CORE_LIBS + _SERVE_LIBS


def __getattr__(name: str):
    # Lazy load
    import importlib

    if name in _LIBS:
        return importlib.import_module("." + name, __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
