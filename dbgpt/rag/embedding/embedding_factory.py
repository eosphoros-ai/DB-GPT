"""EmbeddingFactory class and DefaultEmbeddingFactory class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Type

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.rag.embedding.embeddings import HuggingFaceEmbeddings

if TYPE_CHECKING:
    from dbgpt.rag.embedding.embeddings import Embeddings


class EmbeddingFactory(BaseComponent, ABC):
    """Abstract base class for EmbeddingFactory."""

    name = "embedding_factory"

    @abstractmethod
    def create(
        self, model_name: Optional[str] = None, embedding_cls: Optional[Type] = None
    ) -> "Embeddings":
        """Create an embedding instance.

        Args:
            model_name (str): The model name.
            embedding_cls (Type): The embedding class.

        Returns:
            Embeddings: The embedding instance.
        """


class DefaultEmbeddingFactory(EmbeddingFactory):
    """The default embedding factory."""

    def __init__(
        self,
        system_app: Optional[SystemApp] = None,
        default_model_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Create a new DefaultEmbeddingFactory."""
        super().__init__(system_app=system_app)
        self._default_model_name = default_model_name
        self.kwargs = kwargs

    def init_app(self, system_app):
        """Init the app."""
        pass

    def create(
        self, model_name: Optional[str] = None, embedding_cls: Optional[Type] = None
    ) -> "Embeddings":
        """Create an embedding instance.

        Args:
            model_name (str): The model name.
            embedding_cls (Type): The embedding class.
        """
        if not model_name:
            model_name = self._default_model_name

        new_kwargs = {k: v for k, v in self.kwargs.items()}
        new_kwargs["model_name"] = model_name

        if embedding_cls:
            return embedding_cls(**new_kwargs)
        else:
            return HuggingFaceEmbeddings(**new_kwargs)
