"""Connector for vector store."""

import os
from typing import Any, Dict, List, Optional, Type, cast

from dbgpt.core import Chunk
from dbgpt.core.awel.flow import (
    FunctionDynamicOptions,
    OptionValue,
    Parameter,
    ResourceCategory,
    register_resource,
)
from dbgpt.storage import vector_store
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _

connector: Dict[str, Type] = {}


def _load_vector_options() -> List[OptionValue]:
    return [
        OptionValue(label=cls, name=cls, value=cls)
        for cls in vector_store.__all__
        if issubclass(getattr(vector_store, cls), VectorStoreBase)
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
        vector_store_config: Optional[VectorStoreConfig] = None,
    ) -> None:
        """Create a VectorStoreConnector instance.

        Args:
            - vector_store_type: vector store type Milvus, Chroma, Weaviate
            - ctx: vector store config params.
        """
        self._vector_store_config = vector_store_config
        self._register()

        if self._match(vector_store_type):
            self.connector_class = connector[vector_store_type]
        else:
            raise Exception(f"Vector Store Type Not support. {0}", vector_store_type)

        print(self.connector_class)
        self.client = self.connector_class(vector_store_config)

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
            self._vector_store_config.max_chunks_once_load
            if self._vector_store_config
            else 10
        )
        max_threads = (
            self._vector_store_config.max_threads if self._vector_store_config else 1
        )
        return self.client.load_document_with_limit(
            chunks,
            max_chunks_once_load,
            max_threads,
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

    @property
    def vector_store_config(self) -> VectorStoreConfig:
        """Return the vector store config."""
        if not self._vector_store_config:
            raise ValueError("vector store config not set.")
        return self._vector_store_config

    def vector_name_exists(self):
        """Whether vector name exists."""
        return self.client.vector_name_exists()

    def delete_vector_name(self, vector_name: str):
        """Delete vector name.

        Args:
            - vector_name: vector store name
        """
        return self.client.delete_vector_name(vector_name)

    def delete_by_ids(self, ids):
        """Delete vector by ids.

        Args:
            - ids: vector ids
        """
        return self.client.delete_by_ids(ids=ids)

    def _match(self, vector_store_type) -> bool:
        return bool(connector.get(vector_store_type))

    def _register(self):
        for cls in vector_store.__all__:
            if issubclass(getattr(vector_store, cls), VectorStoreBase):
                _k, _v = cls, getattr(vector_store, cls)
                connector.update({_k: _v})
