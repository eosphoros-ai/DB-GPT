import os
from typing import Any, Callable, List, Optional

from dbgpt.rag.chunk import Chunk
from dbgpt.storage import vector_store
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig

connector = {}


class VectorStoreConnector:

    """VectorStoreConnector, can connect different vector db provided load document api_v1 and similar search api_v1.
    1.load_document:knowledge document source into vector store.(Chroma, Milvus, Weaviate)
    2.similar_search: similarity search from vector_store
    3.similar_search_with_scores: similarity search with similarity score from vector_store

    code example:
    >>> from dbgpt.storage.vector_store.connector import VectorStoreConnector

    >>> vector_store_config = VectorStoreConfig
    >>> vector_store_connector = VectorStoreConnector(vector_store_type="Chroma")
    """

    def __init__(
        self, vector_store_type: str, vector_store_config: VectorStoreConfig = None
    ) -> None:
        """initialize vector store connector.
        Args:
            - vector_store_type: vector store type Milvus, Chroma, Weaviate
            - ctx: vector store config params.
        """
        self._vector_store_config = vector_store_config
        self._register()

        if self._match(vector_store_type):
            self.connector_class = connector.get(vector_store_type)
        else:
            raise Exception(f"Vector Store Type Not support. {0}", vector_store_type)

        print(self.connector_class)
        self.client = self.connector_class(vector_store_config)

    @classmethod
    def from_default(
        cls,
        vector_store_type: str = None,
        embedding_fn: Optional[Any] = None,
        vector_store_config: Optional[VectorStoreConfig] = None,
    ) -> "VectorStoreConnector":
        """initialize default vector store connector."""
        vector_store_type = vector_store_type or os.getenv(
            "VECTOR_STORE_TYPE", "Chroma"
        )
        from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig

        vector_store_config = vector_store_config or ChromaVectorConfig()
        vector_store_config.embedding_fn = embedding_fn
        return cls(vector_store_type, vector_store_config)

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """load document in vector database.
        Args:
            - chunks: document chunks.
        Return chunk ids.
        """
        return self.client.load_document(chunks)

    def similar_search(self, doc: str, topk: int) -> List[Chunk]:
        """similar search in vector database.
        Args:
           - doc: query text
           - topk: topk
        Return:
            - chunks: chunks.
        """
        return self.client.similar_search(doc, topk)

    def similar_search_with_scores(
        self, doc: str, topk: int, score_threshold: float
    ) -> List[Chunk]:
        """
        similar_search_with_score in vector database..
        Return docs and relevance scores in the range [0, 1].
        Args:
            - doc(str): query text
            - topk(int): return docs nums. Defaults to 4.
            - score_threshold(float): score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs,0 is dissimilar, 1 is most similar.
        Return:
            - chunks: chunks.
        """
        return self.client.similar_search_with_scores(doc, topk, score_threshold)

    @property
    def vector_store_config(self) -> VectorStoreConfig:
        """vector store config."""
        return self._vector_store_config

    def vector_name_exists(self):
        """is vector store name exist."""
        return self.client.vector_name_exists()

    def delete_vector_name(self, vector_name):
        """vector store delete
        Args:
            - vector_name: vector store name
        """
        return self.client.delete_vector_name(vector_name)

    def delete_by_ids(self, ids):
        """vector store delete by ids.
        Args:
            - ids: vector ids
        """
        return self.client.delete_by_ids(ids=ids)

    def _match(self, vector_store_type) -> bool:
        if connector.get(vector_store_type):
            return True
        else:
            return False

    def _register(self):
        for cls in vector_store.__all__:
            if issubclass(getattr(vector_store, cls), VectorStoreBase):
                _k, _v = cls, getattr(vector_store, cls)
                connector.update({_k: _v})
