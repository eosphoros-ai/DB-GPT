import logging
from typing import Dict, List, Optional, Type, Union

from dbgpt.configs.model_config import get_device
from dbgpt.core import Embeddings, ModelMetadata, RerankEmbeddings
from dbgpt.core.interface.parameter import (
    BaseDeployModelParameters,
    EmbeddingDeployModelParameters,
    RerankerDeployModelParameters,
)
from dbgpt.model.adapter.base import EmbeddingModelAdapter, get_embedding_adapter
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.model.parameter import (
    WorkerType,
)
from dbgpt.util.model_utils import _clear_model_cache

logger = logging.getLogger(__name__)


class EmbeddingsModelWorker(ModelWorker):
    def __init__(self, rerank_model: bool = False) -> None:
        self._embeddings_impl: Union[Embeddings, RerankEmbeddings, None] = None
        self._model_params: Optional[
            Union[EmbeddingDeployModelParameters, RerankerDeployModelParameters]
        ] = None
        self._param_cls: Optional[
            Union[
                Type[EmbeddingDeployModelParameters],
                Type[RerankerDeployModelParameters],
            ]
        ] = None
        self._adapter: Optional[EmbeddingModelAdapter] = None

        self.model_name: str = ""
        self.model_path: str = ""
        self._rerank_model = rerank_model
        self._device = get_device()

    def load_worker(
        self,
        model_name: str,
        deploy_model_params: BaseDeployModelParameters,
        **kwargs,
    ) -> None:
        self.model_name = model_name
        if isinstance(
            deploy_model_params, EmbeddingDeployModelParameters
        ) or isinstance(deploy_model_params, RerankerDeployModelParameters):
            self._model_params = deploy_model_params
            self._param_cls = deploy_model_params.__class__
            self.model_path = deploy_model_params.real_provider_model_name
            self._adapter = get_embedding_adapter(
                deploy_model_params.provider,
                self._rerank_model,
                self.model_name,
                self.model_path,
            )
            if self._model_params.real_device:
                # Assign device from model params
                self._device = self._model_params.real_device
        else:
            raise ValueError(
                f"Invalid deploy_model_params type: {type(deploy_model_params)}"
            )

    def worker_type(self) -> WorkerType:
        return WorkerType.TEXT2VEC

    def model_param_class(self) -> Type[BaseDeployModelParameters]:
        return self._param_cls

    def start(
        self,
        command_args: List[str] = None,
    ) -> None:
        """Start model worker"""

        if self._rerank_model:
            logger.info(f"Load rerank embeddings model: {self.model_name}")
            self._embeddings_impl = self._adapter.load_from_params(self._model_params)
        else:
            logger.info(f"Load embeddings model: {self.model_name}")
            self._embeddings_impl = self._adapter.load_from_params(self._model_params)

    def __del__(self):
        self.stop()

    def stop(self) -> None:
        if not self._embeddings_impl:
            return
        del self._embeddings_impl
        self._embeddings_impl = None
        _clear_model_cache(self._device)

    def generate_stream(self, params: Dict):
        """Generate stream result, chat scene"""
        raise NotImplementedError("Not supported generate_stream for embeddings model")

    def generate(self, params: Dict):
        """Generate non stream result"""
        raise NotImplementedError("Not supported generate for embeddings model")

    def count_token(self, prompt: str) -> int:
        raise NotImplementedError("Not supported count_token for embeddings model")

    def get_model_metadata(self, params: Dict) -> ModelMetadata:
        raise NotImplementedError(
            "Not supported get_model_metadata for embeddings model"
        )

    def embeddings(self, params: Dict) -> List[List[float]]:
        model = params.get("model")
        logger.info(f"Receive embeddings request, model: {model}")
        textx: List[str] = params["input"]
        if isinstance(self._embeddings_impl, RerankEmbeddings):
            query = params["query"]
            scores: List[float] = self._embeddings_impl.predict(query, textx)
            return [scores]
        else:
            return self._embeddings_impl.embed_documents(textx)


class RerankerModelWorker(EmbeddingsModelWorker):
    def __init__(self) -> None:
        super().__init__(rerank_model=True)

    def worker_type(self) -> WorkerType:
        return WorkerType.RERANKER
