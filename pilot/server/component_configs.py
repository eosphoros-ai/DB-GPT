from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Type

from pilot.component import ComponentType, SystemApp
from pilot.embedding_engine.embedding_factory import EmbeddingFactory
from pilot.server.base import WebWerverParameters

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


logger = logging.getLogger(__name__)


def initialize_components(
    param: WebWerverParameters,
    system_app: SystemApp,
    embedding_model_name: str,
    embedding_model_path: str,
):
    from pilot.model.cluster.controller.controller import controller

    system_app.register_instance(controller)

    _initialize_embedding_model(
        param, system_app, embedding_model_name, embedding_model_path
    )


def _initialize_embedding_model(
    param: WebWerverParameters,
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
        from pilot.model.cluster import WorkerManagerFactory
        from pilot.model.cluster.embedding.remote_embedding import RemoteEmbeddings

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
        from pilot.model.cluster.embedding.loader import EmbeddingLoader
        from pilot.model.cluster.worker.embedding_worker import _parse_embedding_params
        from pilot.model.parameter import (
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
