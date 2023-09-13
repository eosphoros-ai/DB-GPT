from typing import Any, Type, TYPE_CHECKING

from pilot.componet import SystemApp
from pilot.embedding_engine.embedding_factory import EmbeddingFactory

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


def initialize_componets(system_app: SystemApp, embedding_model_name: str):
    from pilot.model.cluster import worker_manager

    system_app.register(
        RemoteEmbeddingFactory, worker_manager, model_name=embedding_model_name
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
