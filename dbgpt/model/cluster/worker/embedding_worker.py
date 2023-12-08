import logging
from typing import Dict, List, Type, Optional

from dbgpt.configs.model_config import get_device
from dbgpt.model.loader import _get_model_real_path
from dbgpt.model.parameter import (
    EmbeddingModelParameters,
    BaseEmbeddingModelParameters,
    WorkerType,
    EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG,
)
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.model.cluster.embedding.loader import EmbeddingLoader
from dbgpt.util.model_utils import _clear_model_cache
from dbgpt.util.parameter_utils import EnvArgumentParser

logger = logging.getLogger(__name__)


class EmbeddingsModelWorker(ModelWorker):
    def __init__(self) -> None:
        try:
            from langchain.embeddings import HuggingFaceEmbeddings
            from langchain.embeddings.base import Embeddings
        except ImportError as exc:
            raise ImportError(
                "Could not import langchain.embeddings.HuggingFaceEmbeddings python package. "
                "Please install it with `pip install langchain`."
            ) from exc
        self._embeddings_impl: Embeddings = None
        self._model_params = None
        self.model_name = None
        self.model_path = None
        self._loader = EmbeddingLoader()

    def load_worker(self, model_name: str, model_path: str, **kwargs) -> None:
        if model_path.endswith("/"):
            model_path = model_path[:-1]
        model_path = _get_model_real_path(model_name, model_path)

        self.model_name = model_name
        self.model_path = model_path

    def worker_type(self) -> WorkerType:
        return WorkerType.TEXT2VEC

    def model_param_class(self) -> Type:
        return EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG.get(
            self.model_name, EmbeddingModelParameters
        )

    def parse_parameters(
        self, command_args: List[str] = None
    ) -> BaseEmbeddingModelParameters:
        param_cls = self.model_param_class()
        return _parse_embedding_params(
            model_name=self.model_name,
            model_path=self.model_path,
            command_args=command_args,
            param_cls=param_cls,
        )

    def start(
        self,
        model_params: EmbeddingModelParameters = None,
        command_args: List[str] = None,
    ) -> None:
        """Start model worker"""
        if not model_params:
            model_params = self.parse_parameters(command_args)
        self._model_params = model_params
        self._embeddings_impl = self._loader.load(self.model_name, model_params)

    def __del__(self):
        self.stop()

    def stop(self) -> None:
        if not self._embeddings_impl:
            return
        del self._embeddings_impl
        self._embeddings_impl = None
        _clear_model_cache(self._model_params.device)

    def generate_stream(self, params: Dict):
        """Generate stream result, chat scene"""
        raise NotImplementedError("Not supported generate_stream for embeddings model")

    def generate(self, params: Dict):
        """Generate non stream result"""
        raise NotImplementedError("Not supported generate for embeddings model")

    def embeddings(self, params: Dict) -> List[List[float]]:
        model = params.get("model")
        logger.info(f"Receive embeddings request, model: {model}")
        input: List[str] = params["input"]
        return self._embeddings_impl.embed_documents(input)


def _parse_embedding_params(
    model_name: str,
    model_path: str,
    command_args: List[str] = None,
    param_cls: Optional[Type] = EmbeddingModelParameters,
):
    model_args = EnvArgumentParser()
    env_prefix = EnvArgumentParser.get_env_prefix(model_name)
    model_params: BaseEmbeddingModelParameters = model_args.parse_args_into_dataclass(
        param_cls,
        env_prefixes=[env_prefix],
        command_args=command_args,
        model_name=model_name,
        model_path=model_path,
    )
    if not model_params.device:
        model_params.device = get_device()
        logger.info(
            f"[EmbeddingsModelWorker] Parameters of device is None, use {model_params.device}"
        )
    return model_params
