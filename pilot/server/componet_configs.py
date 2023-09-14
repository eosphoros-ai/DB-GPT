from typing import Any, Type, TYPE_CHECKING

from pilot.componet import SystemApp
import logging
from pilot.configs.model_config import get_device
from pilot.embedding_engine.embedding_factory import (
    EmbeddingFactory,
    DefaultEmbeddingFactory,
)
from pilot.server.base import WebWerverParameters
from pilot.utils.parameter_utils import EnvArgumentParser

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


logger = logging.getLogger(__name__)


def initialize_componets(
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
    from pilot.model.cluster import worker_manager

    if param.remote_embedding:
        logger.info("Register remote RemoteEmbeddingFactory")
        system_app.register(
            RemoteEmbeddingFactory, worker_manager, model_name=embedding_model_name
        )
    else:
        from pilot.model.parameter import EmbeddingModelParameters
        from pilot.model.cluster.worker.embedding_worker import _parse_embedding_params

        model_params: EmbeddingModelParameters = _parse_embedding_params(
            model_name=embedding_model_name,
            model_path=embedding_model_path,
            param_cls=EmbeddingModelParameters,
        )
        kwargs = model_params.build_kwargs(model_name=embedding_model_path)
        logger.info(f"Register local DefaultEmbeddingFactory with kwargs: {kwargs}")
        system_app.register(
            DefaultEmbeddingFactory, default_model_name=embedding_model_path, **kwargs
        )


class RemoteEmbeddingFactory(EmbeddingFactory):
    def __init__(
        self, system_app, worker_manager, model_name: str = None, **kwargs: Any
    ) -> None:
        super().__init__(system_app=system_app)
        self._worker_manager = worker_manager
        self._default_model_name = model_name
        self.kwargs = kwargs

    def init_app(self, system_app):
        pass

    def create(
        self, model_name: str = None, embedding_cls: Type = None
    ) -> "Embeddings":
        from pilot.model.cluster.embedding.remote_embedding import RemoteEmbeddings

        if embedding_cls:
            raise NotImplementedError
        # Ignore model_name args
        return RemoteEmbeddings(self._default_model_name, self._worker_manager)
