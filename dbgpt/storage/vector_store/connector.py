"""Connector for vector store."""

import copy
import logging
import os
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Tuple, Type, cast

from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import (
    FunctionDynamicOptions,
    OptionValue,
    Parameter,
    ResourceCategory,
    register_resource,
)
from dbgpt.rag.index.base import IndexStoreBase, IndexStoreConfig
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)

connector: Dict[str, Tuple[Type, Type]] = {}
pools: DefaultDict[str, Dict] = defaultdict(dict)


def _load_vector_options() -> List[OptionValue]:
    from dbgpt.storage import vector_store

    return [
        OptionValue(label=cls, name=cls, value=cls)
        for cls in vector_store.__all__
        if issubclass(getattr(vector_store, cls)[0], IndexStoreBase)
    ]


@register_resource(
    _("Vector Store Connector"),
    "vector_store_connector",
    category=ResourceCategory.VECTOR_STORE,
    parameters=[
        Parameter.build_from(
            _("Vector Store Type"),
            "vector_store_type",
            str,
            description=_("The type of vector store."),
            options=FunctionDynamicOptions(func=_load_vector_options),
        ),
        Parameter.build_from(
            _("Vector Store Implementation"),
            "vector_store_config",
            VectorStoreConfig,
            description=_("The vector store implementation."),
            optional=True,
            default=None,
        ),
    ],
)
class VectorStoreConnector:
    """The connector for vector store.

    VectorStoreConnector, can connect different vector db provided load document api_v1
    and similar search api_v1.

    1.load_document:knowledge document source into vector store.(Chroma, Milvus,
    Weaviate).
    2.similar_search: similarity search from vector_store.
    3.similar_search_with_scores: similarity search with similarity score from
    vector_store

    code example:
    >>> from dbgpt.storage.vector_store.connector import VectorStoreConnector

    >>> vector_store_config = VectorStoreConfig
    >>> vector_store_connector = VectorStoreConnector(vector_store_type="Chroma")
    """

    def __init__(
        self,
        vector_store_type: str,
        vector_store_config: Optional[IndexStoreConfig] = None,
    ) -> None:
        """Create a VectorStoreConnector instance.

        Args:
            - vector_store_type: vector store type Milvus, Chroma, Weaviate
            - ctx: vector store config params.
        """
        self._index_store_config = vector_store_config
        self._register()

        if self._match(vector_store_type):
            self.connector_class, self.config_class = connector[vector_store_type]
        else:
            raise Exception(f"Vector store {vector_store_type} not supported")

        logger.info(f"VectorStore:{self.connector_class}")
        self._vector_store_type = vector_store_type
        self._embeddings = (
            vector_store_config.embedding_fn if vector_store_config else None
        )

        try:
            if vector_store_config is not None:
                config: IndexStoreConfig = self.config_class()
                config.name = getattr(vector_store_config, "name", "default_name")
                config.embedding_fn = getattr(vector_store_config, "embedding_fn", None)
                config.max_chunks_once_load = getattr(
                    vector_store_config, "max_chunks_once_load", 5
                )
                config.max_threads = getattr(vector_store_config, "max_threads", 4)
                config.user = getattr(vector_store_config, "user", None)
                config.password = getattr(vector_store_config, "password", None)

                # extra
                config_dict = vector_store_config.dict()
                config.llm_client = config_dict.get("llm_client", None)
                config.model_name = config_dict.get("model_name", None)
                if (
                    vector_store_type in pools
                    and config.name in pools[vector_store_type]
                ):
                    self.client = pools[vector_store_type][config.name]
                else:
                    client = self.connector_class(config)
                    pools[vector_store_type][config.name] = self.client = client
                    self.client = client
        except Exception as e:
            logger.error("connect vector store failed: %s", e)
            raise e

    @classmethod
    def from_default(
        cls,
        vector_store_type: Optional[str] = None,
        embedding_fn: Optional[Any] = None,
        vector_store_config: Optional[VectorStoreConfig] = None,
    ) -> "VectorStoreConnector":
        """Initialize default vector store connector."""
        vector_store_type = vector_store_type or os.getenv(
            "VECTOR_STORE_TYPE", "Chroma"
        )
        from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig

        vector_store_config = vector_store_config or ChromaVectorConfig()
        vector_store_config.embedding_fn = embedding_fn
        real_vector_store_type = cast(str, vector_store_type)
        return cls(real_vector_store_type, vector_store_config)

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
        """Load document in vector database.

        Args:
            - chunks: document chunks.
        Return chunk ids.
        """
        return await self.client.aload_document(
            chunks,
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
        from dbgpt.storage import vector_store

        for cls in vector_store.__all__:
            store_cls, config_cls = getattr(vector_store, cls)
            if issubclass(store_cls, IndexStoreBase) and issubclass(
                config_cls, IndexStoreConfig
            ):
                connector[cls] = (store_cls, config_cls)
