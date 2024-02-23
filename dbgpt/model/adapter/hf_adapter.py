import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from dbgpt.core import ModelMessage
from dbgpt.model.adapter.base import LLMModelAdapter, register_model_adapter
from dbgpt.model.base import ModelType

logger = logging.getLogger(__name__)


class NewHFChatModelAdapter(LLMModelAdapter, ABC):
    """Model adapter for new huggingface chat models

    See https://huggingface.co/docs/transformers/main/en/chat_templating

    We can transform the inference chat messages to chat model instead of create a
    prompt template for this model
    """

    def new_adapter(self, **kwargs) -> "NewHFChatModelAdapter":
        return self.__class__()

    def match(
        self,
        model_type: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        if model_type != ModelType.HF:
            return False
        if model_name is None and model_path is None:
            return False
        model_name = model_name.lower() if model_name else None
        model_path = model_path.lower() if model_path else None
        return self.do_match(model_name) or self.do_match(model_path)

    @abstractmethod
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        raise NotImplementedError()

    def check_dependencies(self) -> None:
        """Check if the dependencies are installed

        Raises:
            ValueError: If the dependencies are not installed
        """
        try:
            import transformers
        except ImportError as exc:
            raise ValueError(
                "Could not import depend python package "
                "Please install it with `pip install transformers`."
            ) from exc
        self.check_transformer_version(transformers.__version__)

    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.34.0":
            raise ValueError(
                "Current model (Load by NewHFChatModelAdapter) require transformers.__version__>=4.34.0"
            )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        try:
            import transformers
            from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise ValueError(
                "Could not import depend python package "
                "Please install it with `pip install transformers`."
            ) from exc
        self.check_dependencies()

        revision = from_pretrained_kwargs.get("revision", "main")
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                use_fast=self.use_fast_tokenizer(),
                revision=revision,
                trust_remote_code=True,
            )
        except TypeError:
            tokenizer = AutoTokenizer.from_pretrained(
                model_path, use_fast=False, revision=revision, trust_remote_code=True
            )
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_path, low_cpu_mem_usage=True, **from_pretrained_kwargs
            )
        except NameError:
            model = AutoModel.from_pretrained(
                model_path, low_cpu_mem_usage=True, **from_pretrained_kwargs
            )
        # tokenizer.use_default_system_prompt = False
        return model, tokenizer

    def get_generate_stream_function(self, model, model_path: str):
        """Get the generate stream function of the model"""
        from dbgpt.model.llm_out.hf_chat_llm import huggingface_chat_generate_stream

        return huggingface_chat_generate_stream

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        from transformers import AutoTokenizer

        if not tokenizer:
            raise ValueError("tokenizer is is None")
        tokenizer: AutoTokenizer = tokenizer

        messages = self.transform_model_messages(messages, convert_to_compatible_format)
        logger.debug(f"The messages after transform: \n{messages}")
        str_prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return str_prompt


class YiAdapter(NewHFChatModelAdapter):
    support_4bit: bool = True
    support_8bit: bool = True
    support_system_message: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "yi-" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )


class Mixtral8x7BAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1
    """

    support_4bit: bool = True
    support_8bit: bool = True
    support_system_message: bool = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "mixtral" in lower_model_name_or_path
            and "8x7b" in lower_model_name_or_path
        )


class SOLARAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/upstage/SOLAR-10.7B-Instruct-v1.0
    """

    support_4bit: bool = True
    support_8bit: bool = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "solar-" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
        )


class GemmaAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/google/gemma-7b-it

    TODO: There are problems with quantization.
    """

    support_4bit: bool = False
    support_8bit: bool = False
    support_system_message: bool = False

    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.38.0":
            raise ValueError(
                "Gemma require transformers.__version__>=4.38.0, please upgrade your transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "gemma-" in lower_model_name_or_path
            and "it" in lower_model_name_or_path
        )


register_model_adapter(YiAdapter)
register_model_adapter(Mixtral8x7BAdapter)
register_model_adapter(SOLARAdapter)
register_model_adapter(GemmaAdapter)
