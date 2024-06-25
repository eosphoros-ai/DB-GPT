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

    trust_remote_code: bool = True

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
                trust_remote_code=self.trust_remote_code,
            )
        except TypeError:
            tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                use_fast=False,
                revision=revision,
                trust_remote_code=self.trust_remote_code,
            )
        try:
            if "trust_remote_code" not in from_pretrained_kwargs:
                from_pretrained_kwargs["trust_remote_code"] = self.trust_remote_code
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


class Yi15Adapter(YiAdapter):
    """Yi 1.5 model adapter."""

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "yi-" in lower_model_name_or_path
            and "1.5" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        str_prompt = super().get_str_prompt(
            params,
            messages,
            tokenizer,
            prompt_template,
            convert_to_compatible_format,
        )
        terminators = [
            tokenizer.eos_token_id,
        ]
        exist_token_ids = params.get("stop_token_ids", [])
        terminators.extend(exist_token_ids)
        params["stop_token_ids"] = terminators
        return str_prompt


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


class StarlingLMAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/Nexusflow/Starling-LM-7B-beta
    """

    support_4bit: bool = True
    support_8bit: bool = True
    support_system_message: bool = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "starling-" in lower_model_name_or_path
            and "lm" in lower_model_name_or_path
        )

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        str_prompt = super().get_str_prompt(
            params,
            messages,
            tokenizer,
            prompt_template,
            convert_to_compatible_format,
        )
        chat_mode = None
        if params and "context" in params and "chat_mode" in params["context"]:
            chat_mode = params["context"].get("chat_mode")
        if chat_mode in [
            "chat_dashboard",
            "chat_with_db_execute",
            "excel_learning",
            "chat_excel",
        ]:
            # Coding conversation, use code prompt
            # This is a temporary solution, we should use a better way to distinguish the conversation type
            # https://huggingface.co/Nexusflow/Starling-LM-7B-beta#code-examples
            str_prompt = str_prompt.replace("GPT4 Correct User:", "Code User:").replace(
                "GPT4 Correct Assistant:", "Code Assistant:"
            )
            logger.info(
                f"Use code prompt for chat_mode: {chat_mode}, transform 'GPT4 Correct User:' to 'Code User:' "
                "and 'GPT4 Correct Assistant:' to 'Code Assistant:'"
            )
        return str_prompt


class QwenAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/Qwen/Qwen1.5-32B-Chat

    TODO: There are problems with quantization.
    """

    support_4bit: bool = True
    support_8bit: bool = False  # TODO: Support 8bit quantization

    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.37.0":
            raise ValueError(
                "Qwen 1.5 require transformers.__version__>=4.37.0, please upgrade your transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "qwen" in lower_model_name_or_path
            and "1.5" in lower_model_name_or_path
            and "moe" not in lower_model_name_or_path
            and "qwen2" not in lower_model_name_or_path
        )


class Qwen2Adapter(QwenAdapter):
    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "qwen2" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
        )


class QwenMoeAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/Qwen/Qwen1.5-MoE-A2.7B

    TODO: There are problems with quantization.
    """

    support_4bit: bool = False
    support_8bit: bool = False

    def check_transformer_version(self, current_version: str) -> None:
        print(f"Checking version: Current version {current_version}")
        if not current_version >= "4.40.0":
            raise ValueError(
                "Qwen 1.5 Moe require transformers.__version__>=4.40.0, please upgrade your transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "qwen" in lower_model_name_or_path
            and "1.5" in lower_model_name_or_path
            and "moe" in lower_model_name_or_path
        )


class Llama3Adapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct
    https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct
    """

    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "llama-3" in lower_model_name_or_path

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        str_prompt = super().get_str_prompt(
            params,
            messages,
            tokenizer,
            prompt_template,
            convert_to_compatible_format,
        )
        terminators = [
            tokenizer.eos_token_id,
            tokenizer.convert_tokens_to_ids("<|eot_id|>"),
        ]
        exist_token_ids = params.get("stop_token_ids", [])
        terminators.extend(exist_token_ids)
        # TODO(fangyinc): We should modify the params in the future
        params["stop_token_ids"] = terminators
        return str_prompt


class DeepseekV2Adapter(NewHFChatModelAdapter):
    support_4bit: bool = False
    support_8bit: bool = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "deepseek" in lower_model_name_or_path
            and "v2" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        if not from_pretrained_kwargs:
            from_pretrained_kwargs = {}
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = True
        model, tokenizer = super().load(model_path, from_pretrained_kwargs)

        from transformers import GenerationConfig

        model.generation_config = GenerationConfig.from_pretrained(model_path)
        model.generation_config.pad_token_id = model.generation_config.eos_token_id
        return model, tokenizer


class SailorAdapter(QwenAdapter):
    """
    https://huggingface.co/sail/Sailor-14B-Chat
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "sailor" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )


class PhiAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/microsoft/Phi-3-medium-128k-instruct
    """

    support_4bit: bool = True
    support_8bit: bool = True
    support_system_message: bool = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "phi-3" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
        )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        if not from_pretrained_kwargs:
            from_pretrained_kwargs = {}
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = True
        return super().load(model_path, from_pretrained_kwargs)

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        str_prompt = super().get_str_prompt(
            params,
            messages,
            tokenizer,
            prompt_template,
            convert_to_compatible_format,
        )
        params["custom_stop_words"] = ["<|end|>"]
        return str_prompt


class SQLCoderAdapter(Llama3Adapter):
    """
    https://huggingface.co/defog/llama-3-sqlcoder-8b
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "llama-3" in lower_model_name_or_path
            and "sqlcoder" in lower_model_name_or_path
        )


class OpenChatAdapter(Llama3Adapter):
    """
    https://huggingface.co/openchat/openchat-3.6-8b-20240522
    """

    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "openchat" in lower_model_name_or_path
            and "3.6" in lower_model_name_or_path
        )


class GLM4Aapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/defog/glm-4-8b
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "glm-4" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )


# The following code is used to register the model adapter
# The last registered model adapter is matched first
register_model_adapter(YiAdapter)
register_model_adapter(Yi15Adapter)
register_model_adapter(Mixtral8x7BAdapter)
register_model_adapter(SOLARAdapter)
register_model_adapter(GemmaAdapter)
register_model_adapter(StarlingLMAdapter)
register_model_adapter(QwenAdapter)
register_model_adapter(QwenMoeAdapter)
register_model_adapter(Llama3Adapter)
register_model_adapter(DeepseekV2Adapter)
register_model_adapter(SailorAdapter)
register_model_adapter(PhiAdapter)
register_model_adapter(SQLCoderAdapter)
register_model_adapter(OpenChatAdapter)
register_model_adapter(GLM4Aapter)
register_model_adapter(Qwen2Adapter)
