from __future__ import annotations

import logging
from typing import Any, Optional, Type

from dbgpt.component import ComponentType, SystemApp
from dbgpt.core import Embeddings, RerankEmbeddings
from dbgpt.rag.embedding.embedding_factory import (
    EmbeddingFactory,
    RerankEmbeddingFactory,
)

logger = logging.getLogger(__name__)


def _initialize_embedding_model(
    system_app: SystemApp,
    default_embedding_name: Optional[str] = None,
):
    if default_embedding_name:
        logger.info("Register remote RemoteEmbeddingFactory")
        system_app.register(RemoteEmbeddingFactory, model_name=default_embedding_name)


def _initialize_rerank_model(
    system_app: SystemApp,
    default_rerank_model_name: Optional[str] = None,
):
    if default_rerank_model_name:
        logger.info("Register remote RemoteRerankEmbeddingFactory")
        system_app.register(
            RemoteRerankEmbeddingFactory, model_name=default_rerank_model_name
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
