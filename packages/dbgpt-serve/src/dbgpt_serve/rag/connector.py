"""Connector for vector store."""

import copy
import logging
import os
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Tuple, Type, cast

from dbgpt import SystemApp
from dbgpt.core import Chunk, Embeddings
from dbgpt.storage.base import IndexStoreConfig
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt_ext.storage import __document_store__ as supported_full_tet_list
from dbgpt_ext.storage import __knowledge_graph__ as supported_kg_store_list
from dbgpt_ext.storage import __vector_store__ as supported_vector_store_list

logger = logging.getLogger(__name__)

connector: Dict[str, Tuple[Type, Type]] = {}
pools: DefaultDict[str, Dict] = defaultdict(dict)


class VectorStoreConnector:
    """The connector for vector store.

        VectorStoreConnector, can connect different vector db provided load document
        api_v1 and similar search api_v1.

        1.load_document:knowledge document source into vector store.(Chroma, Milvus,
        Weaviate).
        2.similar_search: similarity search from vector_store.
        3.similar_search_with_scores: similarity search with similarity score from
        vector_store

        code example:
        >>> from dbgpt_serve.rag.connector import VectorStoreConnector
    l
        >>> vector_store_config = VectorStoreConfig
        >>> vector_store_connector = VectorStoreConnector(vector_store_type="Chroma")
    """

    def __init__(
        self,
        vector_store_type: str,
        vector_store_config: Optional[IndexStoreConfig] = None,
        system_app: Optional[SystemApp] = None,
    ) -> None:
        """Create a VectorStoreConnector instance.

        Args:
            - vector_store_type: vector store type Milvus, Chroma, Weaviate
            - ctx: vector store config params.
        """
        if vector_store_config is None:
            raise Exception("vector_store_config is required")

        self._index_store_config = vector_store_config
        self._system_app = system_app
        self.app_config = self._system_app.config.configs.get("app_config")
        self._register()

        vector_store_type = self._rewrite_index_store_type(vector_store_type)
        if self._match(vector_store_type):
            self.connector_class, self.config_class = connector[vector_store_type]
        else:
            raise Exception(f"Vector store {vector_store_type} not supported")

        logger.info(f"VectorStore:{self.connector_class}")

        self._vector_store_type = vector_store_type
        self._embeddings = vector_store_config.embedding_fn

        config_dict = self._adapt_storage_config(vector_store_type).to_dict()
        for key in vector_store_config.to_dict().keys():
            value = getattr(vector_store_config, key)
            if value is not None:
                config_dict[key] = value
        # for key, value in vector_store_config.model_extra.items():
        #     if value is not None:
        #         config_dict[key] = value
        config = self.config_class(**config_dict)
        try:
            if vector_store_type in pools and config.name in pools[vector_store_type]:
                self.client = pools[vector_store_type][config.name]
            else:
                client = self.connector_class(config)
                pools[vector_store_type][config.name] = self.client = client
        except Exception as e:
            logger.error("connect vector store failed: %s", e)
            raise e

    def _rewrite_index_store_type(self, index_store_type):
        # Rewrite Knowledge Graph Type
        if self.app_config.rag.storage.graph:
            graph_config = self.app_config.rag.storage.graph
            if (
                hasattr(graph_config, "enable_summary")
                and graph_config.enable_summary.lower() == "true"
            ):
                if index_store_type == "KnowledgeGraph":
                    return "CommunitySummaryKnowledgeGraph"
        return index_store_type

    @classmethod
    def from_default(
        cls,
        vector_store_type: Optional[str] = None,
        embedding_fn: Optional[Any] = None,
        vector_store_config: Optional[VectorStoreConfig] = None,
        system_app: Optional[SystemApp] = None,
    ) -> "VectorStoreConnector":
        """Initialize default vector store connector."""
        vector_store_type = vector_store_type or os.getenv(
            "VECTOR_STORE_TYPE", "Chroma"
        )
        from dbgpt_ext.storage.vector_store.chroma_store import ChromaVectorConfig

        vector_store_config = vector_store_config or ChromaVectorConfig()
        vector_store_config.embedding_fn = embedding_fn
        real_vector_store_type = cast(str, vector_store_type)
        return cls(real_vector_store_type, vector_store_config, system_app)

    @property
    def index_client(self):
        return self.client

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database.

        Args:
            - chunks: document chunks.
        Return chunk ids.
        """
        max_chunks_once_load = (
            self._index_store_config.max_chunks_once_load
            if self._index_store_config
            else 10
        )
        max_threads = (
            self._index_store_config.max_threads if self._index_store_config else 1
        )
        return self.client.load_document_with_limit(
            chunks,
            max_chunks_once_load,
            max_threads,
        )

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Async load document in vector database.

        Args:
            - chunks: document chunks.
        Return chunk ids.
        """
        max_chunks_once_load = (
            self._index_store_config.max_chunks_once_load
            if self._index_store_config
            else 10
        )
        max_threads = (
            self._index_store_config.max_threads if self._index_store_config else 1
        )
        return await self.client.aload_document_with_limit(
            chunks, max_chunks_once_load, max_threads
        )

    def similar_search(
        self, doc: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Similar search in vector database.

        Args:
           - doc: query text
           - topk: topk
           - filters: metadata filters.
        Return:
            - chunks: chunks.
        """
        return self.client.similar_search(doc, topk, filters)

    def similar_search_with_scores(
        self,
        doc: str,
        topk: int,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Similar_search_with_score in vector database.

        Return docs and relevance scores in the range [0, 1].

        Args:
            doc(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value
                between 0 to 1 to filter the resulting set of retrieved docs,0 is
                dissimilar, 1 is most similar.
            filters: metadata filters.
        Return:
            - chunks: Return docs and relevance scores in the range [0, 1].
        """
        return self.client.similar_search_with_scores(
            doc, topk, score_threshold, filters
        )

    async def asimilar_search_with_scores(
        self,
        doc: str,
        topk: int,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Async similar_search_with_score in vector database."""
        return await self.client.asimilar_search_with_scores(
            doc, topk, score_threshold, filters
        )

    @property
    def vector_store_config(self) -> IndexStoreConfig:
        """Return the vector store config."""
        if not self._index_store_config:
            raise ValueError("vector store config not set.")
        return self._index_store_config

    def vector_name_exists(self):
        """Whether vector name exists."""
        return self.client.vector_name_exists()

    def delete_vector_name(self, vector_name: str):
        """Delete vector name.

        Args:
            - vector_name: vector store name
        """
        try:
            if self.vector_name_exists():
                self.client.delete_vector_name(vector_name)
                del pools[self._vector_store_type][vector_name]
        except Exception as e:
            logger.error(f"delete vector name {vector_name} failed: {e}")
            raise Exception(f"delete name {vector_name} failed")
        return True

    def delete_by_ids(self, ids):
        """Delete vector by ids.

        Args:
            - ids: vector ids
        """
        return self.client.delete_by_ids(ids=ids)

    def delete_by_file_id(self, file_id):
        """Delete file by ids.

        Args:
            - ids: vector ids
        """
        return self.client.delete_by_file_id(file_id=file_id)

    def truncate(self):
        """Truncate data."""
        return self.client.truncate()

    @property
    def current_embeddings(self) -> Optional[Embeddings]:
        """Return the current embeddings."""
        return self._embeddings

    def new_connector(self, name: str, **kwargs) -> "VectorStoreConnector":
        """Create a new connector.

        New connector based on the current connector.
        """
        config = copy.copy(self.vector_store_config)
        for k, v in kwargs.items():
            if v is not None:
                setattr(config, k, v)
        config.name = name

        return self.__class__(self._vector_store_type, config)

    def _match(self, vector_store_type) -> bool:
        return bool(connector.get(vector_store_type))

    def _register(self):
        from dbgpt_ext.storage import __all__ as rag_storages
        from dbgpt_ext.storage import _select_rag_storage

        for cls_name in rag_storages:
            store_cls, config_cls = _select_rag_storage(cls_name)
            connector[cls_name] = (store_cls, config_cls)

    def _adapt_storage_config(self, vector_store_type):
        """Adapt storage config."""
        storage_config = self.app_config.rag.storage
        if vector_store_type in supported_vector_store_list:
            return storage_config.vector
        elif vector_store_type in supported_kg_store_list:
            return storage_config.graph
        elif vector_store_type in supported_full_tet_list:
            return storage_config.full_text
        raise ValueError(f"storage type {vector_store_type} not supported")
