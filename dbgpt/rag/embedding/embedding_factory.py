"""EmbeddingFactory class and DefaultEmbeddingFactory class."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Type

from dbgpt.component import BaseComponent, SystemApp

if TYPE_CHECKING:
    from dbgpt.core import Embeddings


logger = logging.getLogger(__name__)


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
        default_model_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Create a new DefaultEmbeddingFactory."""
        super().__init__(system_app=system_app)
        if not default_model_path:
            default_model_path = default_model_name
        if not default_model_name:
            default_model_name = default_model_path
        self._default_model_name = default_model_name
        self._default_model_path = default_model_path
        self._kwargs = kwargs
        self._model = self._load_model()

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
        if embedding_cls:
            raise NotImplementedError
        return self._model

    def _load_model(self) -> "Embeddings":
        from dbgpt.model.adapter.embeddings_loader import (
            EmbeddingLoader,
            _parse_embedding_params,
        )
        from dbgpt.model.parameter import (
            EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG,
            BaseEmbeddingModelParameters,
            EmbeddingModelParameters,
        )

        param_cls = EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG.get(
            self._default_model_name, EmbeddingModelParameters
        )
        model_params: BaseEmbeddingModelParameters = _parse_embedding_params(
            model_name=self._default_model_name,
            model_path=self._default_model_path,
            param_cls=param_cls,
            **self._kwargs,
        )
        logger.info(model_params)
        loader = EmbeddingLoader()
        # Ignore model_name args
        model_name = self._default_model_name or model_params.model_name
        if not model_name:
            raise ValueError("model_name must be provided.")
        return loader.load(model_name, model_params)


class WrappedEmbeddingFactory(EmbeddingFactory):
    """The default embedding factory."""

    def __init__(
        self,
        system_app: Optional[SystemApp] = None,
        embeddings: Optional["Embeddings"] = None,
        **kwargs: Any,
    ) -> None:
        """Create a new DefaultEmbeddingFactory."""
        super().__init__(system_app=system_app)
        if not embeddings:
            raise ValueError("embeddings must be provided.")
        self._model = embeddings

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
        if embedding_cls:
            raise NotImplementedError
        return self._model
