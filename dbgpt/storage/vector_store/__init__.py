"""Vector Store Module."""
from typing import Any


def _import_pgvector() -> Any:
    from dbgpt.storage.vector_store.pgvector_store import PGVectorStore

    return PGVectorStore


def _import_milvus() -> Any:
    from dbgpt.storage.vector_store.milvus_store import MilvusStore

    return MilvusStore


def _import_chroma() -> Any:
    from dbgpt.storage.vector_store.chroma_store import ChromaStore

    return ChromaStore


def _import_weaviate() -> Any:
    from dbgpt.storage.vector_store.weaviate_store import WeaviateStore

    return WeaviateStore


def _import_oceanbase() -> Any:
    from dbgpt.storage.vector_store.oceanbase_store import OceanBaseStore

    return OceanBaseStore


def _import_elastic() -> Any:
    from dbgpt.storage.vector_store.elastic_store import ElasticStore

    return ElasticStore


def __getattr__(name: str) -> Any:
    if name == "Chroma":
        return _import_chroma()
    elif name == "Milvus":
        return _import_milvus()
    elif name == "Weaviate":
        return _import_weaviate()
    elif name == "PGVector":
        return _import_pgvector()
    elif name == "OceanBase":
        return _import_oceanbase()
    elif name == "ElasticSearch":
        return _import_elastic()
    else:
        raise AttributeError(f"Could not find: {name}")


__all__ = ["Chroma", "Milvus", "Weaviate", "OceanBase", "PGVector", "ElasticSearch"]
