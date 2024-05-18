from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, Type

from dbgpt.component import ComponentType, SystemApp
from dbgpt.core import Embeddings, RerankEmbeddings
from dbgpt.rag.embedding.embedding_factory import (
    EmbeddingFactory,
    RerankEmbeddingFactory,
)

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings

    from dbgpt.app.base import WebServerParameters

logger = logging.getLogger(__name__)


def _initialize_embedding_model(
    param: "WebServerParameters",
    system_app: SystemApp,
    embedding_model_name: str,
    embedding_model_path: str,
):
    if param.remote_embedding:
        logger.info("Register remote RemoteEmbeddingFactory")
        system_app.register(RemoteEmbeddingFactory, model_name=embedding_model_name)
    else:
        logger.info(f"Register local LocalEmbeddingFactory")
        system_app.register(
            LocalEmbeddingFactory,
            default_model_name=embedding_model_name,
            default_model_path=embedding_model_path,
        )


def _initialize_rerank_model(
    param: "WebServerParameters",
    system_app: SystemApp,
    rerank_model_name: Optional[str] = None,
    rerank_model_path: Optional[str] = None,
):
    if not rerank_model_name:
        return
    if param.remote_rerank:
        logger.info("Register remote RemoteRerankEmbeddingFactory")
        system_app.register(RemoteRerankEmbeddingFactory, model_name=rerank_model_name)
    else:
        logger.info(f"Register local LocalRerankEmbeddingFactory")
        system_app.register(
            LocalRerankEmbeddingFactory,
            default_model_name=rerank_model_name,
            default_model_path=rerank_model_path,
        )


class RemoteEmbeddingFactory(EmbeddingFactory):
    def __init__(self, system_app, model_name: str = None, **kwargs: Any) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = model_name
        self.kwargs = kwargs
        self.system_app = system_app

    def init_app(self, system_app):
        self.system_app = system_app

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.embedding.remote_embedding import RemoteEmbeddings

        if embedding_cls:
            raise NotImplementedError
        worker_manager = self.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        # Ignore model_name args
        return RemoteEmbeddings(self._default_model_name, worker_manager)


class LocalEmbeddingFactory(EmbeddingFactory):
    def __init__(
        self,
        system_app,
        default_model_name: str = None,
        default_model_path: str = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = default_model_name
        self._default_model_path = default_model_path
        self._kwargs = kwargs
        self._model = self._load_model()

    def init_app(self, system_app):
        pass

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
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
        return loader.load(self._default_model_name, model_params)


class RemoteRerankEmbeddingFactory(RerankEmbeddingFactory):
    def __init__(self, system_app, model_name: str = None, **kwargs: Any) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = model_name
        self.kwargs = kwargs
        self.system_app = system_app

    def init_app(self, system_app):
        self.system_app = system_app

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "RerankEmbeddings":
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.embedding.remote_embedding import (
            RemoteRerankEmbeddings,
        )

        if embedding_cls:
            raise NotImplementedError
        worker_manager = self.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return RemoteRerankEmbeddings(
            model_name or self._default_model_name, worker_manager
        )


class LocalRerankEmbeddingFactory(RerankEmbeddingFactory):
    def __init__(
        self,
        system_app,
        default_model_name: str = None,
        default_model_path: str = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = default_model_name
        self._default_model_path = default_model_path
        self._kwargs = kwargs
        self._model = self._load_model()

    def init_app(self, system_app):
        pass

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "RerankEmbeddings":
        if embedding_cls:
            raise NotImplementedError
        return self._model

    def _load_model(self) -> "RerankEmbeddings":
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
        return loader.load_rerank_model(self._default_model_name, model_params)
