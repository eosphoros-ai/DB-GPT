from abc import ABC, abstractmethod
import math
from typing import Optional, Callable

from pydantic import Field, BaseModel


class VectorStoreConfig(BaseModel):
    """Vector store config."""

    name: str = Field(
        default="dbgpt",
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
    embedding_fn: Optional[Callable] = Field(
        default=None,
        description="The embedding function of vector store, if not set, will use the default embedding function.",
    )


class VectorStoreBase(ABC):
    """base class for vector store database"""

    @abstractmethod
    def load_document(self, documents) -> None:
        """load document in vector database."""
        pass

    @abstractmethod
    def similar_search(self, text, topk) -> None:
        """similar search in vector database."""
        pass

    @abstractmethod
    def vector_name_exists(self) -> bool:
        """is vector store name exist."""
        return False

    @abstractmethod
    def delete_by_ids(self, ids):
        """delete vector by ids."""
        pass

    @abstractmethod
    def delete_vector_name(self, vector_name):
        """delete vector name."""
        pass

    def _normalization_vectors(self, vectors):
        """normalization vectors to scale[0,1]"""
        import numpy as np

        norm = np.linalg.norm(vectors)
        return vectors / norm

    def _default_relevance_score_fn(self, distance: float) -> float:
        """Return a similarity score on a scale [0, 1]."""
        return 1.0 - distance / math.sqrt(2)
