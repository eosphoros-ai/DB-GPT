"""EmbeddingFactory class and DefaultEmbeddingFactory class."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core import Embeddings

logger = logging.getLogger(__name__)


class EmbeddingFactory(BaseComponent, ABC):
    """Abstract base class for EmbeddingFactory."""

    name = "embedding_factory"

    @abstractmethod
    def create(
        self, model_name: Optional[str] = None, embedding_cls: Optional[Type] = None
    ) -> Embeddings:
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
    ) -> Embeddings:
        """Create an embedding instance.

        Args:
            model_name (str): The model name.
            embedding_cls (Type): The embedding class.
        """
        if embedding_cls:
            raise NotImplementedError
        return self._model

    def _load_model(self) -> Embeddings:
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

    @classmethod
    def openai(
        cls,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "text-embedding-3-small",
        timeout: int = 60,
        **kwargs: Any,
    ) -> Embeddings:
        """Create an OpenAI embeddings.

        If api_url and api_key are not provided, we will try to get them from
        environment variables.

        Args:
            api_url (Optional[str], optional): The api url. Defaults to None.
            api_key (Optional[str], optional): The api key. Defaults to None.
            model_name (str, optional): The model name.
                Defaults to "text-embedding-3-small".
            timeout (int, optional): The timeout. Defaults to 60.

        Returns:
            Embeddings: The embeddings instance.
        """
        api_url = (
            api_url
            or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
        )
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("api_key must be provided.")
        return cls.remote(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            **kwargs,
        )

    @classmethod
    def default(
        cls, model_name: str, model_path: Optional[str] = None, **kwargs: Any
    ) -> Embeddings:
        """Create a default embeddings.

        It will try to load the model from the model name or model path.

        Args:
            model_name (str): The model name.
            model_path (Optional[str], optional): The model path. Defaults to None.
                if not provided, it will use the model name as the model path to load
                the model.

        Returns:
            Embeddings: The embeddings instance.
        """
        return cls(
            default_model_name=model_name, default_model_path=model_path, **kwargs
        ).create()

    @classmethod
    def remote(
        cls,
        api_url: str = "http://localhost:8100/api/v1/embeddings",
        api_key: Optional[str] = None,
        model_name: str = "text2vec",
        timeout: int = 60,
        **kwargs: Any,
    ) -> Embeddings:
        """Create a remote embeddings.

        Create a remote embeddings which API compatible with the OpenAI's API. So if
        your model is compatible with OpenAI's API, you can use this method to create
        a remote embeddings.

        Args:
            api_url (str, optional): The api url. Defaults to
                "http://localhost:8100/api/v1/embeddings".
            api_key (Optional[str], optional): The api key. Defaults to None.
            model_name (str, optional): The model name. Defaults to "text2vec".
            timeout (int, optional): The timeout. Defaults to 60.
        """
        from .embeddings import OpenAPIEmbeddings

        return OpenAPIEmbeddings(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            **kwargs,
        )


class WrappedEmbeddingFactory(EmbeddingFactory):
    """The default embedding factory."""

    def __init__(
        self,
        system_app: Optional[SystemApp] = None,
        embeddings: Optional[Embeddings] = None,
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
    ) -> Embeddings:
        """Create an embedding instance.

        Args:
            model_name (str): The model name.
            embedding_cls (Type): The embedding class.
        """
        if embedding_cls:
            raise NotImplementedError
        return self._model
