# Old packages
# __all__ = ["SourceEmbedding", "register", "EmbeddingEngine", "KnowledgeType"]

__all__ = ["embedding_engine"]


def __getattr__(name: str):
    import importlib

    if name in ["embedding_engine"]:
        return importlib.import_module("." + name, __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
