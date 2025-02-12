import logging
from typing import Dict, Optional, Type

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import (
    ConversationAdapter,
    LLMModelAdapter,
    register_model_adapter,
)
from dbgpt.model.adapter.model_metadata import COMMON_LLAMA_CPP_MODELS
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import LlamaCppModelParameters

logger = logging.getLogger(__name__)


class LLamaCppModelAdapter(LLMModelAdapter):
    def model_type(self) -> str:
        return ModelType.LLAMA_CPP

    def model_param_class(
        self, model_type: str = None
    ) -> Type[LlamaCppModelParameters]:
        return LlamaCppModelParameters

    def match(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        if provider != ModelType.LLAMA_CPP:
            return False
        model_name = model_name.lower() if model_name else None
        model_path = model_path.lower() if model_path else None
        return self.do_match(model_name) or self.do_match(model_path)

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "gguf" in lower_model_name_or_path

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        return None

    def load_from_params(self, params: LlamaCppModelParameters):
        try:
            from dbgpt.model.llm.llama_cpp.llama_cpp import LlamaCppModel
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: llama-cpp-python "
                "Please install it by `pip install llama-cpp-python`"
            ) from exc
        model_path = params.real_model_path
        model, tokenizer = LlamaCppModel.from_pretrained(model_path, params)
        return model, tokenizer

    def get_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        return generate_stream


def generate_stream(model, tokenizer, params: Dict, device: str, context_len: int):
    # Just support LlamaCppModel
    return model.generate_streaming(params=params, context_len=context_len)


register_model_adapter(LLamaCppModelAdapter, supported_models=COMMON_LLAMA_CPP_MODELS)
