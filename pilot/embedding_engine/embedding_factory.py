from abc import ABC, abstractmethod
from typing import Any, Type, TYPE_CHECKING

from pilot.componet import BaseComponet

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


class EmbeddingFactory(BaseComponet, ABC):
    name = "embedding_factory"

    @abstractmethod
    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
        """Create embedding"""


class DefaultEmbeddingFactory(EmbeddingFactory):
    def __init__(self, system_app=None, model_name: str = None, **kwargs: Any) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = model_name
        self.kwargs = kwargs

    def init_app(self, system_app):
        pass

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
        if not model_name:
            model_name = self._default_model_name
        if embedding_cls:
            return embedding_cls(model_name=model_name, **self.kwargs)
        else:
            from langchain.embeddings import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(model_name=model_name, **self.kwargs)
