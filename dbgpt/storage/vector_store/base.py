from abc import ABC, abstractmethod
import math
from typing import Optional, Callable, List, Any

from pydantic import Field, BaseModel

from dbgpt.rag.chunk import Chunk


class VectorStoreConfig(BaseModel):
    """Vector store config."""

    name: str = Field(
        default="dbgpt_collection",
        description="The name of vector store, if not set, will use the default name.",
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description="The password of vector store, if not set, will use the default password.",
    )
    embedding_fn: Optional[Any] = Field(
        default=None,
        description="The embedding function of vector store, if not set, will use the default embedding function.",
    )


class VectorStoreBase(ABC):
    """base class for vector store database"""

    @abstractmethod
    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """load document in vector database.
        Args:
            - chunks: document chunks.
        Return:
            - ids: chunks ids.
        """
        pass

    @abstractmethod
    def similar_search(self, text, topk) -> List[Chunk]:
        """similar search in vector database.
        Args:
            - text: query text
            - topk: topk
        Return:
            - chunks: chunks.
        """
        pass

    @abstractmethod
    def similar_search_with_scores(
        self, text, topk, score_threshold: float
    ) -> List[Chunk]:
        """similar search in vector database with scores.
        Args:
            - text: query text
            - topk: topk
            - score_threshold: score_threshold: Optional, a floating point value between 0 to 1
        Return:
            - chunks: chunks.
        """
        pass

    @abstractmethod
    def vector_name_exists(self) -> bool:
        """is vector store name exist."""
        return False

    @abstractmethod
    def delete_by_ids(self, ids):
        """delete vector by ids.
        Args:
            - ids: vector ids
        """

    @abstractmethod
    def delete_vector_name(self, vector_name):
        """delete vector name.
        Args:
            - vector_name: vector store name
        """
        pass

    def _normalization_vectors(self, vectors):
        """normalization vectors to scale[0,1]"""
        import numpy as np

        norm = np.linalg.norm(vectors)
        return vectors / norm

    def _default_relevance_score_fn(self, distance: float) -> float:
        """Return a similarity score on a scale [0, 1]."""
        return 1.0 - distance / math.sqrt(2)
