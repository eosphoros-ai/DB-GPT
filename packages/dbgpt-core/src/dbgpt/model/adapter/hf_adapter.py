import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from dbgpt.core import ModelMessage
from dbgpt.core.interface.parameter import (
    BaseHFQuantization,
    LLMDeployModelParameters,
)
from dbgpt.model.adapter.base import LLMModelAdapter, register_model_adapter
from dbgpt.model.adapter.model_metadata import (
    COMMON_HF_DEEPSEEK__MODELS,
    COMMON_HF_GLM_MODELS,
    COMMON_HF_QWEN25_MODELS,
)
from dbgpt.model.base import ModelType
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@dataclass
class HFLLMDeployModelParameters(LLMDeployModelParameters):
    """Local deploy model parameters."""

    provider: str = "hf"

    path: Optional[str] = field(
        default=None,
        metadata={
            "order": -800,
            "help": _("The path of the model, if you want to deploy a local model."),
        },
    )
    device: Optional[str] = field(
        default=None,
        metadata={
            "order": -700,
            "help": _(
                "Device to run model. If None, the device is automatically determined"
            ),
        },
    )

    trust_remote_code: Optional[bool] = field(
        default=True, metadata={"help": _("Trust remote code or not.")}
    )
    quantization: Optional[BaseHFQuantization] = field(
        default=None,
        metadata={
            "help": _("The quantization parameters."),
        },
    )
    low_cpu_mem_usage: Optional[bool] = field(
        default=None,
        metadata={
            "help": _(
                "Whether to use low CPU memory usage mode. It can reduce the memory "
                "when loading the model, if you load your model with quantization, it "
                "will be True by default. You must install `accelerate` to make it "
                "work."
            )
        },
    )
    num_gpus: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "The number of gpus you expect to use, if it is empty, use all of "
                "them as much as possible"
            )
        },
    )
    max_gpu_memory: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The maximum memory limit of each GPU, only valid in multi-GPU "
                "configuration, eg: 10GiB, 24GiB"
            )
        },
    )
    torch_dtype: Optional[str] = field(
        default=None,
        metadata={
            "help": _("The dtype of the model, default is None."),
            "valid_values": ["auto", "float16", "bfloat16", "float", "float32"],
        },
    )
    attn_implementation: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The attention implementation, only valid in multi-GPU configuration"
            ),
            "valid_values": ["flash_attention_2"],
        },
    )

    @property
    def real_model_path(self) -> Optional[str]:
        """Get the real model path.

        If deploy model is not local, return None.
        """
        return self._resolve_root_path(self.path)

    @property
    def real_device(self) -> Optional[str]:
        """Get the real device."""
        return self.device or super().real_device


class NewHFChatModelAdapter(LLMModelAdapter, ABC):
    """Model adapter for new huggingface chat models

    See https://huggingface.co/docs/transformers/main/en/chat_templating

    We can transform the inference chat messages to chat model instead of create a
    prompt template for this model
    """

    trust_remote_code: bool = True

    def match(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        if provider != ModelType.HF:
            return False
        if model_name is None and model_path is None:
            return False
        model_name = model_name.lower() if model_name else None
        model_path = model_path.lower() if model_path else None
        return self.do_match(model_name) or self.do_match(model_path)

    def model_param_class(
        self, model_type: str = None
    ) -> Type[LLMDeployModelParameters]:
        return HFLLMDeployModelParameters

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
                "Current model (Load by NewHFChatModelAdapter) require "
                "transformers.__version__>=4.34.0"
            )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        try:
            import transformers  # noqa: F401
            from transformers import (
                AutoModel,
                AutoModelForCausalLM,
            )
        except ImportError as exc:
            raise ValueError(
                "Could not import depend python package "
                "Please install it with `pip install transformers`."
            ) from exc
        self.check_dependencies()

        logger.info(
            f"Load model from {model_path}, from_pretrained_kwargs: "
            f"{from_pretrained_kwargs}"
        )

        revision = from_pretrained_kwargs.get("revision", "main")
        trust_remote_code = from_pretrained_kwargs.get(
            "trust_remote_code", self.trust_remote_code
        )
        low_cpu_mem_usage = from_pretrained_kwargs.get("low_cpu_mem_usage", False)
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = trust_remote_code
        if "low_cpu_mem_usage" not in from_pretrained_kwargs:
            from_pretrained_kwargs["low_cpu_mem_usage"] = low_cpu_mem_usage

        tokenizer = self.load_tokenizer(
            model_path,
            revision,
            use_fast=self.use_fast_tokenizer(),
            trust_remote_code=trust_remote_code,
        )
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                **from_pretrained_kwargs,
            )
        except NameError:
            model = AutoModel.from_pretrained(
                model_path,
                **from_pretrained_kwargs,
            )
        return model, tokenizer

    def load_tokenizer(
        self,
        model_path: str,
        revision: Optional[str] = None,
        use_fast: bool = False,
        trust_remote_code: bool = False,
    ):
        from transformers import (
            AutoProcessor,
            AutoTokenizer,
        )

        try:
            return AutoProcessor.from_pretrained(
                model_path,
                use_fast=use_fast,
                revision=revision,
                trust_remote_code=trust_remote_code,
            )
        except Exception as _e:
            pass

        try:
            return AutoTokenizer.from_pretrained(
                model_path,
                use_fast=use_fast,
                revision=revision,
                trust_remote_code=trust_remote_code,
            )
        except TypeError:
            return AutoTokenizer.from_pretrained(
                model_path,
                use_fast=False,
                revision=revision,
                trust_remote_code=trust_remote_code,
            )

    def load_from_params(self, params: LLMDeployModelParameters):
        """Load the model from the parameters."""
        from .loader import huggingface_loader

        return huggingface_loader(self, params)

    def get_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        """Get the generate stream function of the model"""
        from dbgpt.model.llm.llm_out.hf_chat_llm import huggingface_chat_generate_stream

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

    def load_media(self, params: Dict, messages: List[ModelMessage]):
        """Load the media from the messages.
        Args:
            params: The parameters of the model.
            messages: The messages to load.
            tokenizer: The tokenizer to use.
        """
        from dbgpt.model.utils.media_utils import parse_messages

        results = parse_messages(messages)
        if "images" in results and results["images"]:
            params["images"] = results["images"]
        if "videos" in results and results["videos"]:
            params["videos"] = results["videos"]
        if "audios" in results and results["audios"]:
            params["audios"] = results["audios"]


class CommonModelAdapter(NewHFChatModelAdapter):
    """Common model adapter for huggingface chat models.

    It is the last one to check if the model is a huggingface chat model.
    """

    support_4bit: bool = True
    support_8bit: bool = True
    support_system_message: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path is not None


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


class MistralNemo(NewHFChatModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "mistral" in lower_model_name_or_path
            and "nemo" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
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
                "Gemma require transformers.__version__>=4.38.0, please upgrade your "
                "transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "gemma-" in lower_model_name_or_path
            and "it" in lower_model_name_or_path
        )


class Gemma2Adapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/google/gemma-2-27b-it
    https://huggingface.co/google/gemma-2-9b-it
    """

    support_4bit: bool = True
    support_8bit: bool = True
    support_system_message: bool = False

    def use_fast_tokenizer(self) -> bool:
        return True

    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.42.1":
            raise ValueError(
                "Gemma2 require transformers.__version__>=4.42.1, please upgrade your "
                "transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "gemma-2-" in lower_model_name_or_path
            and "it" in lower_model_name_or_path
        )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        import torch

        if not from_pretrained_kwargs:
            from_pretrained_kwargs = {}
        from_pretrained_kwargs["torch_dtype"] = torch.bfloat16
        # from_pretrained_kwargs["revision"] = "float16"
        model, tokenizer = super().load(model_path, from_pretrained_kwargs)
        return model, tokenizer


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
            # This is a temporary solution, we should use a better way to distinguish
            # the conversation type
            # https://huggingface.co/Nexusflow/Starling-LM-7B-beta#code-examples
            str_prompt = str_prompt.replace("GPT4 Correct User:", "Code User:").replace(
                "GPT4 Correct Assistant:", "Code Assistant:"
            )
            logger.info(
                f"Use code prompt for chat_mode: {chat_mode}, transform 'GPT4 Correct "
                "User:' to 'Code User:' and 'GPT4 Correct Assistant:' to "
                "'Code Assistant:'"
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
                "Qwen 1.5 require transformers.__version__>=4.37.0, please upgrade your"
                " transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "qwen" in lower_model_name_or_path
            and "1.5" in lower_model_name_or_path
            and "moe" not in lower_model_name_or_path
            and "qwen2" not in lower_model_name_or_path
            and "vl" not in lower_model_name_or_path
        )


class Qwen2Adapter(QwenAdapter):
    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and (
            (
                "qwen2" in lower_model_name_or_path
                and "instruct" in lower_model_name_or_path
                and "vl" not in lower_model_name_or_path
            )
            or (
                "qwen2.5" in lower_model_name_or_path
                and "instruct" in lower_model_name_or_path
                and "vl" not in lower_model_name_or_path
            )
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
                "Qwen 1.5 Moe require transformers.__version__>=4.40.0, please upgrade"
                " your transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "qwen" in lower_model_name_or_path
            and "1.5" in lower_model_name_or_path
            and "moe" in lower_model_name_or_path
        )


class Qwen3Adapter(QwenAdapter):
    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and (
            "qwen3" in lower_model_name_or_path
            and "base" not in lower_model_name_or_path
            and "vl" not in lower_model_name_or_path
        )

    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.51.0":
            raise ValueError(
                "Qwen3 require transformers.__version__>=4.51.0, please upgrade your"
                " transformers package."
            )

    def model_patch(self, deploy_model_params: LLMDeployModelParameters):
        """Apply the monkey patch to moe model for high inference speed."""

        from ..llm.monkey_patch import apply_qwen3_moe_monkey_patch

        return apply_qwen3_moe_monkey_patch

    def is_reasoning_model(
        self,
        deploy_model_params: LLMDeployModelParameters,
        lower_model_name_or_path: Optional[str] = None,
    ) -> bool:
        if (
            deploy_model_params.reasoning_model is not None
            and deploy_model_params.reasoning_model is False
        ):
            return False
        return True

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

        is_reasoning_model = params.get("is_reasoning_model", True)
        messages = self.transform_model_messages(
            messages, convert_to_compatible_format, support_media_content=False
        )
        logger.debug(f"The messages after transform: \n{messages}")
        str_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=is_reasoning_model,
        )
        return str_prompt


class Qwen2VLAdapter(NewHFChatModelAdapter):
    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.37.0":
            raise ValueError(
                "Qwen2.5VL model require transformers.__version__>=4.37.0, please "
                "upgrade your transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "qwen2" in lower_model_name_or_path
            and "vl" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
        )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        try:
            from transformers import (
                Qwen2_5_VLForConditionalGeneration,
            )
        except ImportError as exc:
            raise ValueError(
                "Could not import qwen2.5 vl model, please upgrade your "
                "transformers package to 4.37.0 or later."
            ) from exc

        logger.info(
            f"Load model from {model_path}, from_pretrained_kwargs: "
            f"{from_pretrained_kwargs}"
        )

        revision = from_pretrained_kwargs.get("revision", "main")
        trust_remote_code = from_pretrained_kwargs.get(
            "trust_remote_code", self.trust_remote_code
        )
        low_cpu_mem_usage = from_pretrained_kwargs.get("low_cpu_mem_usage", False)
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = trust_remote_code
        if "low_cpu_mem_usage" not in from_pretrained_kwargs:
            from_pretrained_kwargs["low_cpu_mem_usage"] = low_cpu_mem_usage

        tokenizer = self.load_tokenizer(
            model_path,
            revision,
            use_fast=self.use_fast_tokenizer(),
            trust_remote_code=trust_remote_code,
        )
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_path, **from_pretrained_kwargs
        )
        return model, tokenizer


class QwenOmniAdapter(NewHFChatModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and (
            "qwen" in lower_model_name_or_path and "omni" in lower_model_name_or_path
        )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        try:
            from transformers import (
                AutoModel,
                Qwen2_5OmniForConditionalGeneration,
                Qwen2_5OmniProcessor,
            )
        except ImportError as exc:
            raise ValueError(
                "Could not import qwen2.5 omni model, please upgrade your "
                "transformers package to 4.51.4 or later."
            ) from exc
        logger.info(
            f"Load model from {model_path}, from_pretrained_kwargs: "
            f"{from_pretrained_kwargs}"
        )

        revision = from_pretrained_kwargs.get("revision", "main")
        trust_remote_code = from_pretrained_kwargs.get(
            "trust_remote_code", self.trust_remote_code
        )
        low_cpu_mem_usage = from_pretrained_kwargs.get("low_cpu_mem_usage", False)
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = trust_remote_code
        if "low_cpu_mem_usage" not in from_pretrained_kwargs:
            from_pretrained_kwargs["low_cpu_mem_usage"] = low_cpu_mem_usage
        tokenizer = Qwen2_5OmniProcessor.from_pretrained(
            model_path,
            revision=revision,
            use_fast=self.use_fast_tokenizer(),
            trust_remote_code=trust_remote_code,
        )
        try:
            model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
                model_path, **from_pretrained_kwargs
            )
        except NameError:
            model = AutoModel.from_pretrained(
                model_path,
                **from_pretrained_kwargs,
            )
        return model, tokenizer

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        messages = self.transform_model_messages(messages, convert_to_compatible_format)
        sys_messages = []
        other_messages = []
        for message in messages:
            if message["role"] == "system":
                sys_messages.append(message)
            else:
                other_messages.append(message)
        if sys_messages and isinstance(sys_messages[0]["content"], str):
            sys_messages[0]["content"] = [
                {"type": "text", "text": sys_messages[0]["content"]}
            ]
        new_messages = sys_messages + other_messages
        logger.debug(f"The messages after transform: \n{messages}")
        str_prompt = tokenizer.apply_chat_template(
            new_messages, tokenize=False, add_generation_prompt=True
        )
        return str_prompt[0] if isinstance(str_prompt, list) else str_prompt


class Llama3Adapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct
    https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct
    """

    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "llama-3" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
            and "3.1" not in lower_model_name_or_path
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
            tokenizer.convert_tokens_to_ids("<|eot_id|>"),
        ]
        exist_token_ids = params.get("stop_token_ids", [])
        terminators.extend(exist_token_ids)
        # TODO(fangyinc): We should modify the params in the future
        params["stop_token_ids"] = terminators
        return str_prompt


class Llama31Adapter(Llama3Adapter):
    def check_transformer_version(self, current_version: str) -> None:
        logger.info(f"Checking transformers version: Current version {current_version}")
        if not current_version >= "4.43.0":
            raise ValueError(
                "Llama-3.1 require transformers.__version__>=4.43.0, please upgrade "
                "your transformers package."
            )

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "llama-3.1" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
        )


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


class DeepseekCoderV2Adapter(DeepseekV2Adapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "deepseek" in lower_model_name_or_path
            and "coder" in lower_model_name_or_path
            and "v2" in lower_model_name_or_path
            and "instruct" in lower_model_name_or_path
        )


class DeepseekV3R1Adapter(DeepseekV2Adapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "deepseek" in lower_model_name_or_path
            and ("v3" in lower_model_name_or_path or "r1" in lower_model_name_or_path)
        )


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


class GLM4Adapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/THUDM/glm-4-9b-chat
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "glm-4" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )


class GLM40414Adapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/collections/THUDM/glm-4-0414-67f3cbcb34dd9d252707cb2e
    """

    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "glm-4" in lower_model_name_or_path
            and "0414" in lower_model_name_or_path
            and "base" not in lower_model_name_or_path
        ) or (lower_model_name_or_path and "glm-z1" in lower_model_name_or_path)

    def use_fast_tokenizer(self) -> bool:
        return True

    def is_reasoning_model(
        self,
        deploy_model_params: LLMDeployModelParameters,
        lower_model_name_or_path: Optional[str] = None,
    ) -> bool:
        if (
            deploy_model_params.reasoning_model is not None
            and deploy_model_params.reasoning_model
        ):
            return True
        return lower_model_name_or_path and "z1" in lower_model_name_or_path


class GLM41VAdapter(GLM40414Adapter):
    """
    https://huggingface.co/THUDM/GLM-4.1V-9B-Thinking
    Please make sure your transformers version is >= 4.54.0, and you can install it with
    following command:
    uv pip install git+https://github.com/huggingface/transformers.git
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "glm-4.1v" in lower_model_name_or_path

    def is_reasoning_model(
        self,
        deploy_model_params: LLMDeployModelParameters,
        lower_model_name_or_path: Optional[str] = None,
    ) -> bool:
        if (
            deploy_model_params.reasoning_model is not None
            and deploy_model_params.reasoning_model
        ):
            return True
        return lower_model_name_or_path and "thinking" in lower_model_name_or_path

    def check_transformer_version(self, current_version: str) -> None:
        if not current_version >= "4.54.0":
            raise ValueError(
                "GLM-4.1V require transformers.__version__>= 4.54.0, please upgrade "
                "your transformers package."
                "And you can install transformers with "
                "`uv pip install git+https://github.com/huggingface/transformers.git`"
            )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        try:
            from transformers import (
                Glm4vForConditionalGeneration,
            )
        except ImportError as exc:
            raise ValueError(
                "Could not import glm-4.1v model, please upgrade your "
                "transformers package to 4.54.0 or later."
            ) from exc

        logger.info(
            f"Load model from {model_path}, from_pretrained_kwargs: "
            f"{from_pretrained_kwargs}"
        )

        revision = from_pretrained_kwargs.get("revision", "main")
        trust_remote_code = from_pretrained_kwargs.get(
            "trust_remote_code", self.trust_remote_code
        )
        low_cpu_mem_usage = from_pretrained_kwargs.get("low_cpu_mem_usage", False)
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = trust_remote_code
        if "low_cpu_mem_usage" not in from_pretrained_kwargs:
            from_pretrained_kwargs["low_cpu_mem_usage"] = low_cpu_mem_usage
        model = Glm4vForConditionalGeneration.from_pretrained(
            model_path, **from_pretrained_kwargs
        )
        tokenizer = self.load_tokenizer(
            model_path,
            revision,
            use_fast=self.use_fast_tokenizer(),
            trust_remote_code=trust_remote_code,
        )
        return model, tokenizer

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
        type_mapping = {
            "image_url": "image",
        }
        messages = self.transform_model_messages(
            messages, convert_to_compatible_format, type_mapping=type_mapping
        )
        logger.debug(f"The messages after transform: \n{messages}")
        str_prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return str_prompt


class Codegeex4Adapter(GLM4Adapter):
    """
    https://huggingface.co/THUDM/codegeex4-all-9b
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "codegeex4" in lower_model_name_or_path

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        if not from_pretrained_kwargs:
            from_pretrained_kwargs = {}
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = True
        return super().load(model_path, from_pretrained_kwargs)


class Internlm2Adapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/internlm/internlm2_5-7b-chat
    """

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return (
            lower_model_name_or_path
            and "internlm2" in lower_model_name_or_path
            and "chat" in lower_model_name_or_path
        )

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        if not from_pretrained_kwargs:
            from_pretrained_kwargs = {}
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = True
        return super().load(model_path, from_pretrained_kwargs)


class KimiVLAdapter(NewHFChatModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "kimi-vl" in lower_model_name_or_path

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
        params["think_start_token"] = "◁think▷"
        params["think_end_token"] = "◁/think▷"
        return str_prompt

    def is_reasoning_model(
        self,
        deploy_model_params: LLMDeployModelParameters,
        lower_model_name_or_path: Optional[str] = None,
    ) -> bool:
        if (
            deploy_model_params.reasoning_model is not None
            and deploy_model_params.reasoning_model
        ):
            return True
        return lower_model_name_or_path and "thinking" in lower_model_name_or_path


class MiniCPMAdapter(NewHFChatModelAdapter):
    """
    https://huggingface.co/openbmb/MiniCPM4-8B
    """

    support_4bit: bool = True
    support_8bit: bool = True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "minicpm" in lower_model_name_or_path

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        if not from_pretrained_kwargs:
            from_pretrained_kwargs = {}
        if "trust_remote_code" not in from_pretrained_kwargs:
            from_pretrained_kwargs["trust_remote_code"] = True
        return super().load(model_path, from_pretrained_kwargs)


# The following code is used to register the model adapter
# The last registered model adapter is matched first
register_model_adapter(CommonModelAdapter)  # For all of hf models can be matched
register_model_adapter(YiAdapter)
register_model_adapter(Yi15Adapter)
register_model_adapter(Mixtral8x7BAdapter)
register_model_adapter(MistralNemo)
register_model_adapter(SOLARAdapter)
register_model_adapter(GemmaAdapter)
register_model_adapter(Gemma2Adapter)
register_model_adapter(StarlingLMAdapter)
register_model_adapter(QwenAdapter)
register_model_adapter(QwenMoeAdapter)
register_model_adapter(Qwen3Adapter)
register_model_adapter(QwenOmniAdapter)
register_model_adapter(Llama3Adapter)
register_model_adapter(Llama31Adapter)
register_model_adapter(DeepseekV2Adapter)
register_model_adapter(DeepseekCoderV2Adapter)
register_model_adapter(SailorAdapter)
register_model_adapter(PhiAdapter)
register_model_adapter(SQLCoderAdapter)
register_model_adapter(OpenChatAdapter)
register_model_adapter(GLM4Adapter, supported_models=COMMON_HF_GLM_MODELS)
register_model_adapter(GLM40414Adapter)
register_model_adapter(GLM41VAdapter)
register_model_adapter(Codegeex4Adapter)
register_model_adapter(Qwen2Adapter, supported_models=COMMON_HF_QWEN25_MODELS)
register_model_adapter(Qwen2VLAdapter)
register_model_adapter(Internlm2Adapter)
register_model_adapter(DeepseekV3R1Adapter, supported_models=COMMON_HF_DEEPSEEK__MODELS)
register_model_adapter(KimiVLAdapter)
register_model_adapter(MiniCPMAdapter)
