"""Module of RAG storage."""

from typing import Tuple, Type


def _import_pgvector() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.vector_store.pgvector_store import (
        PGVectorConfig,
        PGVectorStore,
    )

    return PGVectorStore, PGVectorConfig


def _import_milvus() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.vector_store.milvus_store import (
        MilvusStore,
        MilvusVectorConfig,
    )

    return MilvusStore, MilvusVectorConfig


def _import_chroma() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.vector_store.chroma_store import (
        ChromaStore,
        ChromaVectorConfig,
    )

    return ChromaStore, ChromaVectorConfig


def _import_weaviate() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.vector_store.weaviate_store import (
        WeaviateStore,
        WeaviateVectorConfig,
    )

    return WeaviateStore, WeaviateVectorConfig


def _import_oceanbase() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.vector_store.oceanbase_store import (
        OceanBaseConfig,
        OceanBaseStore,
    )

    return OceanBaseStore, OceanBaseConfig


def _import_elastic() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.vector_store.elastic_store import (
        ElasticsearchStoreConfig,
        ElasticStore,
    )

    return ElasticStore, ElasticsearchStoreConfig


def _import_builtin_knowledge_graph() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.knowledge_graph.knowledge_graph import (
        BuiltinKnowledgeGraph,
        BuiltinKnowledgeGraphConfig,
    )

    return BuiltinKnowledgeGraph, BuiltinKnowledgeGraphConfig


def _import_community_summary_knowledge_graph() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.knowledge_graph.community_summary import (
        CommunitySummaryKnowledgeGraph,
        CommunitySummaryKnowledgeGraphConfig,
    )

    return CommunitySummaryKnowledgeGraph, CommunitySummaryKnowledgeGraphConfig


def _import_openspg() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.knowledge_graph.open_spg import OpenSPG, OpenSPGConfig

    return OpenSPG, OpenSPGConfig


def _import_full_text() -> Tuple[Type, Type]:
    from dbgpt_ext.storage.full_text.elasticsearch import ElasticDocumentStore
    from dbgpt_ext.storage.vector_store.elastic_store import ElasticsearchStoreConfig

    return ElasticDocumentStore, ElasticsearchStoreConfig


def _select_rag_storage(name: str) -> Tuple[Type, Type]:
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
    elif name == "CommunitySummaryKnowledgeGraph":
        return _import_community_summary_knowledge_graph()
    elif name == "OpenSPG":
        return _import_openspg()
    elif name == "FullText":
        return _import_full_text()
    else:
        raise AttributeError(f"Could not find: {name}")


_HAS_SCAN = False


def scan_storage_configs():
    """Scan storage configs."""
    from dbgpt.storage.base import IndexStoreConfig
    from dbgpt.util.module_utils import ModelScanner, ScannerConfig

    global _HAS_SCAN

    if _HAS_SCAN:
        return
    modules = [
        "dbgpt_ext.storage.vector_store",
        "dbgpt_ext.storage.knowledge_graph",
        "dbgpt_ext.storage.graph_store",
    ]

    scanner = ModelScanner[IndexStoreConfig]()
    for module in modules:
        config = ScannerConfig(
            module_path=module,
            base_class=IndexStoreConfig,
        )
        scanner.scan_and_register(config)
    _HAS_SCAN = True
    return scanner.get_registered_items()


__vector_store__ = [
    "Chroma",
    "Milvus",
    "Weaviate",
    "OceanBase",
    "PGVector",
    "ElasticSearch",
]

__knowledge_graph__ = ["KnowledgeGraph", "CommunitySummaryKnowledgeGraph", "OpenSPG"]

__document_store__ = ["FullText"]

__all__ = __vector_store__ + __knowledge_graph__ + __document_store__
