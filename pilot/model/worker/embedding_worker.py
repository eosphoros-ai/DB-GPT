import logging
from typing import Dict, List, Type

from pilot.configs.model_config import get_device
from pilot.model.loader import _get_model_real_path
from pilot.model.parameter import (
    EmbeddingModelParameters,
    WorkerType,
)
from pilot.model.worker.base import ModelWorker
from pilot.utils.model_utils import _clear_torch_cache
from pilot.utils.parameter_utils import EnvArgumentParser

logger = logging.getLogger("model_worker")


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
        self.embeddings: Embeddings = None
        self._model_params = None

    def load_worker(self, model_name: str, model_path: str, **kwargs) -> None:
        if model_path.endswith("/"):
            model_path = model_path[:-1]
        model_path = _get_model_real_path(model_name, model_path)

        self.model_name = model_name
        self.model_path = model_path

    def worker_type(self) -> WorkerType:
        return WorkerType.TEXT2VEC

    def model_param_class(self) -> Type:
        return EmbeddingModelParameters

    def parse_parameters(
        self, command_args: List[str] = None
    ) -> EmbeddingModelParameters:
        param_cls = self.model_param_class()
        model_args = EnvArgumentParser()
        env_prefix = EnvArgumentParser.get_env_prefix(self.model_name)
        model_params: EmbeddingModelParameters = model_args.parse_args_into_dataclass(
            param_cls,
            env_prefix=env_prefix,
            command_args=command_args,
            model_name=self.model_name,
            model_path=self.model_path,
        )
        if not model_params.device:
            model_params.device = get_device()
            logger.info(
                f"[EmbeddingsModelWorker] Parameters of device is None, use {model_params.device}"
            )
        return model_params

    def start(
        self,
        model_params: EmbeddingModelParameters = None,
        command_args: List[str] = None,
    ) -> None:
        """Start model worker"""
        from langchain.embeddings import HuggingFaceEmbeddings

        if not model_params:
            model_params = self.parse_parameters(command_args)
        self._model_params = model_params

        kwargs = model_params.build_kwargs(model_name=model_params.model_path)
        logger.info(f"Start HuggingFaceEmbeddings with kwargs: {kwargs}")
        self.embeddings = HuggingFaceEmbeddings(**kwargs)

    def __del__(self):
        self.stop()

    def stop(self) -> None:
        if not self.embeddings:
            return
        del self.embeddings
        self.embeddings = None
        _clear_torch_cache(self._model_params.device)

    def generate_stream(self, params: Dict):
        """Generate stream result, chat scene"""
        raise NotImplementedError("Not supported generate_stream for embeddings model")

    def generate(self, params: Dict):
        """Generate non stream result"""
        raise NotImplementedError("Not supported generate for embeddings model")

    def embeddings(self, params: Dict) -> List[List[float]]:
        input: List[str] = params["input"]
        return self.embeddings.embed_documents(input)
