"""Vector Store Module."""
from typing import Type


def _import_pgvector() -> (Type, Type):
    from dbgpt.storage.vector_store.pgvector_store import PGVectorStore
    from dbgpt.storage.vector_store.pgvector_store import PGVectorConfig
    return PGVectorStore, PGVectorConfig


def _import_milvus() -> (Type, Type):
    from dbgpt.storage.vector_store.milvus_store import MilvusStore
    from dbgpt.storage.vector_store.milvus_store import MilvusVectorConfig
    return MilvusStore, MilvusVectorConfig


def _import_chroma() -> (Type, Type):
    from dbgpt.storage.vector_store.chroma_store import ChromaStore
    from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
    return ChromaStore, ChromaVectorConfig


def _import_weaviate() -> (Type, Type):
    from dbgpt.storage.vector_store.weaviate_store import WeaviateStore
    from dbgpt.storage.vector_store.weaviate_store import WeaviateVectorConfig
    return WeaviateStore, WeaviateVectorConfig


def _import_oceanbase() -> (Type, Type):
    from dbgpt.storage.vector_store.oceanbase_store import OceanBaseStore
    from dbgpt.storage.vector_store.oceanbase_store import OceanBaseConfig
    return OceanBaseStore, OceanBaseConfig


def _import_elastic() -> (Type, Type):
    from dbgpt.storage.vector_store.elastic_store import ElasticStore
    from dbgpt.storage.vector_store.elastic_store import \
        ElasticsearchVectorConfig
    return ElasticStore, ElasticsearchVectorConfig


def _import_builtin_knowledge_graph() -> (Type, Type):
    from dbgpt.storage.knowledge_graph.knowledge_graph import \
        BuiltinKnowledgeGraph
    from dbgpt.storage.knowledge_graph.knowledge_graph import \
        BuiltinKnowledgeGraphConfig
    return BuiltinKnowledgeGraph, BuiltinKnowledgeGraphConfig


def _import_openspg() -> (Type, Type):
    from dbgpt.storage.knowledge_graph.open_spg import OpenSPG
    from dbgpt.storage.knowledge_graph.open_spg import OpenSPGConfig
    return OpenSPG, OpenSPGConfig


def __getattr__(name: str) -> (Type, Type):
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
    elif name == "KnowledgeGraph":
        return _import_builtin_knowledge_graph()
    elif name == "OpenSPG":
        return _import_openspg()
    else:
        raise AttributeError(f"Could not find: {name}")


__vector_store__ = [
    "Chroma", "Milvus", "Weaviate", "OceanBase", "PGVector", "ElasticSearch"
]

__knowledge_graph__ = [
    "KnowledgeGraph", "OpenSPG"
]

__all__ = __vector_store__ + __knowledge_graph__
