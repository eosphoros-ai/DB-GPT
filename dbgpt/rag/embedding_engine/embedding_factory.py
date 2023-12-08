from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Type, TYPE_CHECKING

from dbgpt.component import BaseComponent

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


class EmbeddingFactory(BaseComponent, ABC):
    name = "embedding_factory"

    @abstractmethod
    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
        """Create embedding"""


class DefaultEmbeddingFactory(EmbeddingFactory):
    def __init__(
        self, system_app=None, default_model_name: str = None, **kwargs: Any
    ) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = default_model_name
        self.kwargs = kwargs

    def init_app(self, system_app):
        pass

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
        if not model_name:
            model_name = self._default_model_name

        new_kwargs = {k: v for k, v in self.kwargs.items()}
        new_kwargs["model_name"] = model_name

        if embedding_cls:
            return embedding_cls(**new_kwargs)
        else:
            from langchain.embeddings import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(**new_kwargs)
