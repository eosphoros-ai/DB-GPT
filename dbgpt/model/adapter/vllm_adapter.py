import dataclasses
import logging

from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.model.adapter.template import ConversationAdapter, ConversationAdapterFactory
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import BaseModelParameters
from dbgpt.util.parameter_utils import (
    _build_parameter_class,
    _extract_parameter_details,
    _get_dataclass_print_str,
)

logger = logging.getLogger(__name__)


class VLLMModelAdapterWrapper(LLMModelAdapter):
    """Wrapping vllm engine"""

    def __init__(self, conv_factory: ConversationAdapterFactory):
        self.conv_factory = conv_factory

    def new_adapter(self, **kwargs) -> "VLLMModelAdapterWrapper":
        return VLLMModelAdapterWrapper(self.conv_factory)

    def model_type(self) -> str:
        return ModelType.VLLM

    def model_param_class(self, model_type: str = None) -> BaseModelParameters:
        import argparse

        from vllm.engine.arg_utils import AsyncEngineArgs

        parser = argparse.ArgumentParser()
        parser = AsyncEngineArgs.add_cli_args(parser)
        parser.add_argument("--model_name", type=str, help="model name")
        parser.add_argument(
            "--model_path",
            type=str,
            help="local model path of the huggingface model to use",
        )
        parser.add_argument("--model_type", type=str, help="model type")
        parser.add_argument("--device", type=str, default=None, help="device")
        # TODO parse prompt templete from `model_name` and `model_path`
        parser.add_argument(
            "--prompt_template",
            type=str,
            default=None,
            help="Prompt template. If None, the prompt template is automatically determined from model path",
        )

        descs = _extract_parameter_details(
            parser,
            "dbgpt.model.parameter.VLLMModelParameters",
            skip_names=["model"],
            overwrite_default_values={"trust_remote_code": True},
        )
        return _build_parameter_class(descs)

    def load_from_params(self, params):
        import torch
        from vllm import AsyncLLMEngine
        from vllm.engine.arg_utils import AsyncEngineArgs

        num_gpus = torch.cuda.device_count()
        if num_gpus > 1 and hasattr(params, "tensor_parallel_size"):
            setattr(params, "tensor_parallel_size", num_gpus)
        logger.info(
            f"Start vllm AsyncLLMEngine with args: {_get_dataclass_print_str(params)}"
        )

        params = dataclasses.asdict(params)
        params["model"] = params["model_path"]
        attrs = [attr.name for attr in dataclasses.fields(AsyncEngineArgs)]
        vllm_engine_args_dict = {attr: params.get(attr) for attr in attrs}
        # Set the attributes from the parsed arguments.
        engine_args = AsyncEngineArgs(**vllm_engine_args_dict)
        engine = AsyncLLMEngine.from_engine_args(engine_args)
        return engine, engine.engine.tokenizer

    def support_async(self) -> bool:
        return True

    def get_async_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.llm_out.vllm_llm import generate_stream

        return generate_stream

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> ConversationAdapter:
        return self.conv_factory.get_by_model(model_name, model_path)

    def __str__(self) -> str:
        return "{}.{}".format(self.__class__.__module__, self.__class__.__name__)
