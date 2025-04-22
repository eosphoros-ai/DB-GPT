"""RAG STORAGE MANAGER manager."""

from typing import List, Optional, Type

from dbgpt import BaseComponent
from dbgpt.component import ComponentType, SystemApp
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.embedding import EmbeddingFactory
from dbgpt.storage.base import IndexStoreBase
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig
from dbgpt_ext.storage.full_text.elasticsearch import ElasticDocumentStore
from dbgpt_ext.storage.knowledge_graph.knowledge_graph import BuiltinKnowledgeGraph


class StorageManager(BaseComponent):
    """RAG STORAGE MANAGER manager."""

    name = ComponentType.RAG_STORAGE_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new ConnectorManager."""
        self.system_app = system_app
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Init component."""
        self.system_app = system_app

    def storage_config(self):
        """Storage config."""
        app_config = self.system_app.config.configs.get("app_config")
        return app_config.rag.storage

    def get_storage_connector(
        self, index_name: str, storage_type: str, llm_model: Optional[str] = None
    ) -> IndexStoreBase:
        """Get storage connector."""
        supported_vector_types = self.get_vector_supported_types
        storage_config = self.storage_config()
        if storage_type.lower() in supported_vector_types:
            return self.create_vector_store(index_name)
        elif storage_type == "KnowledgeGraph":
            if not storage_config.graph:
                raise ValueError(
                    "Graph storage is not configured.please check your config."
                    "reference configs/dbgpt-graphrag.toml"
                )
            return self.create_kg_store(index_name, llm_model)
        elif storage_type == "FullText":
            if not storage_config.full_text:
                raise ValueError(
                    "FullText storage is not configured.please check your config."
                    "reference configs/dbgpt-bm25-rag.toml"
                )
            return self.create_full_text_store(index_name)
        else:
            raise ValueError(f"Does not support storage type {storage_type}")

    def create_vector_store(self, index_name) -> VectorStoreBase:
        """Create vector store."""
        app_config = self.system_app.config.configs.get("app_config")
        storage_config = app_config.rag.storage
        embedding_factory = self.system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create()
        vector_store_config: VectorStoreConfig = storage_config.vector
        return vector_store_config.create_store(
            name=index_name,
            embedding_fn=embedding_fn,
            max_chunks_once_load=vector_store_config.max_chunks_once_load,
            max_threads=vector_store_config.max_threads,
        )

    def create_kg_store(
        self, index_name, llm_model: Optional[str] = None
    ) -> BuiltinKnowledgeGraph:
        """Create knowledge graph store."""
        app_config = self.system_app.config.configs.get("app_config")
        rag_config = app_config.rag
        storage_config = app_config.rag.storage
        worker_manager = self.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        llm_client = DefaultLLMClient(worker_manager=worker_manager)
        embedding_factory = self.system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create()
        if storage_config.graph:
            graph_config = storage_config.graph
            graph_config.llm_model = llm_model
            if hasattr(graph_config, "enable_summary") and graph_config.enable_summary:
                from dbgpt_ext.storage.knowledge_graph.community_summary import (
                    CommunitySummaryKnowledgeGraph,
                )

                return CommunitySummaryKnowledgeGraph(
                    config=storage_config.graph,
                    name=index_name,
                    llm_client=llm_client,
                    vector_store_config=storage_config.vector,
                    kg_extract_top_k=rag_config.kg_extract_top_k,
                    kg_extract_score_threshold=rag_config.kg_extract_score_threshold,
                    kg_community_top_k=rag_config.kg_community_top_k,
                    kg_community_score_threshold=rag_config.kg_community_score_threshold,
                    kg_triplet_graph_enabled=rag_config.kg_triplet_graph_enabled,
                    kg_document_graph_enabled=rag_config.kg_document_graph_enabled,
                    kg_chunk_search_top_k=rag_config.kg_chunk_search_top_k,
                    kg_extraction_batch_size=rag_config.kg_extraction_batch_size,
                    kg_community_summary_batch_size=rag_config.kg_community_summary_batch_size,
                    kg_embedding_batch_size=rag_config.kg_embedding_batch_size,
                    kg_similarity_top_k=rag_config.kg_similarity_top_k,
                    kg_similarity_score_threshold=rag_config.kg_similarity_score_threshold,
                    kg_enable_text_search=rag_config.kg_enable_text_search,
                    kg_text2gql_model_enabled=rag_config.kg_text2gql_model_enabled,
                    kg_text2gql_model_name=rag_config.kg_text2gql_model_name,
                    embedding_fn=embedding_fn,
                    kg_max_chunks_once_load=rag_config.max_chunks_once_load,
                    kg_max_threads=rag_config.max_threads,
                )
        return BuiltinKnowledgeGraph(
            config=storage_config.graph,
            name=index_name,
            llm_client=llm_client,
        )

    def create_full_text_store(self, index_name) -> FullTextStoreBase:
        """Create Full Text store."""
        app_config = self.system_app.config.configs.get("app_config")
        rag_config = app_config.rag
        storage_config = app_config.rag.storage
        return ElasticDocumentStore(
            es_config=storage_config.full_text,
            name=index_name,
            k1=rag_config.bm25_k1,
            b=rag_config.bm25_b,
        )

    @property
    def get_vector_supported_types(self) -> List[str]:
        """Get all supported types."""
        support_types = []
        vector_store_classes = _get_all_subclasses()
        for vector_cls in vector_store_classes:
            support_types.append(vector_cls.__type__)
        return support_types


def _get_all_subclasses() -> List[Type[VectorStoreConfig]]:
    """Get all subclasses of cls."""

    return VectorStoreConfig.__subclasses__()
