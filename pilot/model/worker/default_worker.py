import logging
import platform
from typing import Dict, Iterator, List

import torch
from pilot.configs.model_config import DEVICE
from pilot.model.adapter import get_llm_model_adapter, BaseLLMAdaper
from pilot.model.base import ModelOutput
from pilot.model.loader import ModelLoader, _get_model_real_path
from pilot.model.parameter import EnvArgumentParser, ModelParameters
from pilot.model.worker.base import ModelWorker
from pilot.server.chat_adapter import get_llm_chat_adapter, BaseChatAdpter
from pilot.utils.model_utils import _clear_torch_cache

logger = logging.getLogger("model_worker")


class DefaultModelWorker(ModelWorker):
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self._model_params = None
        self.llm_adapter: BaseLLMAdaper = None
        self.llm_chat_adapter: BaseChatAdpter = None

    def load_worker(self, model_name: str, model_path: str, **kwargs) -> None:
        if model_path.endswith("/"):
            model_path = model_path[:-1]
        model_path = _get_model_real_path(model_name, model_path)
        self.model_name = model_name
        self.model_path = model_path

        self.llm_adapter = get_llm_model_adapter(self.model_name, self.model_path)
        model_type = self.llm_adapter.model_type()
        self.param_cls = self.llm_adapter.model_param_class(model_type)

        self.llm_chat_adapter = get_llm_chat_adapter(self.model_name, self.model_path)
        self.generate_stream_func = self.llm_chat_adapter.get_generate_stream_func(
            self.model_path
        )

        self.ml: ModelLoader = ModelLoader(
            model_path=self.model_path, model_name=self.model_name
        )
        # TODO read context len from model config
        self.context_len = 2048

    def model_param_class(self) -> ModelParameters:
        return self.param_cls

    def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
        param_cls = self.model_param_class()
        model_args = EnvArgumentParser()
        env_prefix = None
        model_type = self.llm_adapter.model_type()
        model_params: ModelParameters = model_args.parse_args_into_dataclass(
            param_cls,
            env_prefix=env_prefix,
            command_args=command_args,
            model_name=self.model_name,
            model_path=self.model_path,
            model_type=model_type,
        )
        if not model_params.device:
            model_params.device = DEVICE
            logger.info(
                f"[DefaultModelWorker] Parameters of device is None, use {model_params.device}"
            )
        return model_params

    def start(
        self, model_params: ModelParameters = None, command_args: List[str] = None
    ) -> None:
        if not model_params:
            model_params = self.parse_parameters(command_args)
        self._model_params = model_params
        logger.info(f"Begin load model, model params: {model_params}")
        self.model, self.tokenizer = self.ml.loader_with_params(model_params)

    def stop(self) -> None:
        if not self.model:
            return
        del self.model
        del self.tokenizer
        self.model = None
        self.tokenizer = None
        _clear_torch_cache(self._model_params.device)

    def generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        try:
            # params adaptation
            params, model_context = self.llm_chat_adapter.model_adaptation(
                params, self.ml.model_path, prompt_template=self.ml.prompt_template
            )

            for output in self.generate_stream_func(
                self.model, self.tokenizer, params, DEVICE, self.context_len
            ):
                # Please do not open the output in production!
                # The gpt4all thread shares stdout with the parent process,
                # and opening it may affect the frontend output.
                if "windows" in platform.platform().lower():
                    # Do not print the model output, because it may contain Emoji, there is a problem with the GBK encoding
                    pass
                else:
                    print("output: ", output)
                # return some model context to dgt-server
                model_output = ModelOutput(
                    text=output, error_code=0, model_context=model_context
                )
                yield model_output

        except torch.cuda.CudaError:
            model_output = ModelOutput(
                text="**GPU OutOfMemory, Please Refresh.**", error_code=0
            )
            yield model_output
        except Exception as e:
            model_output = ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=0,
            )
            yield model_output

    def generate(self, params: Dict) -> ModelOutput:
        """Generate non stream result"""
        output = None
        for out in self.generate_stream(params):
            output = out
        return output

    def embeddings(self, params: Dict) -> List[List[float]]:
        raise NotImplementedError
