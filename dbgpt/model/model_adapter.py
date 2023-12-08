from __future__ import annotations

from typing import Callable, List, Dict, Type, Tuple, TYPE_CHECKING, Any, Optional
import dataclasses
import logging
import threading
import os
from functools import cache
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import (
    ModelParameters,
    LlamaCppModelParameters,
    ProxyModelParameters,
)
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.util.parameter_utils import (
    _extract_parameter_details,
    _build_parameter_class,
    _get_dataclass_print_str,
)

try:
    from fastchat.conversation import (
        Conversation,
        register_conv_template,
        SeparatorStyle,
    )
except ImportError as exc:
    raise ValueError(
        "Could not import python package: fschat "
        "Please install fastchat by command `pip install fschat` "
    ) from exc

if TYPE_CHECKING:
    from fastchat.model.model_adapter import BaseModelAdapter
    from dbgpt.model.adapter import BaseLLMAdaper as OldBaseLLMAdaper
    from torch.nn import Module as TorchNNModule

logger = logging.getLogger(__name__)

thread_local = threading.local()
_IS_BENCHMARK = os.getenv("DB_GPT_MODEL_BENCHMARK", "False").lower() == "true"


_OLD_MODELS = [
    "llama-cpp",
    "proxyllm",
    "gptj-6b",
    "codellama-13b-sql-sft",
    "codellama-7b",
    "codellama-7b-sql-sft",
    "codellama-13b",
]

_NEW_HF_CHAT_MODELS = [
    "yi-34b",
    "yi-6b",
]

# The implementation of some models in fastchat will affect the DB-GPT loading model and will be temporarily added to the blacklist.
_BLACK_LIST_MODLE_PROMPT = ["OpenHermes-2.5-Mistral-7B"]


class LLMModelAdaper:
    """New Adapter for DB-GPT LLM models"""

    def use_fast_tokenizer(self) -> bool:
        """Whether use a [fast Rust-based tokenizer](https://huggingface.co/docs/tokenizers/index) if it is supported
        for a given model.
        """
        return False

    def model_type(self) -> str:
        return ModelType.HF

    def model_param_class(self, model_type: str = None) -> ModelParameters:
        """Get the startup parameters instance of the model"""
        model_type = model_type if model_type else self.model_type()
        if model_type == ModelType.LLAMA_CPP:
            return LlamaCppModelParameters
        elif model_type == ModelType.PROXY:
            return ProxyModelParameters
        return ModelParameters

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        """Load model and tokenizer"""
        raise NotImplementedError

    def load_from_params(self, params):
        """Load the model and tokenizer according to the given parameters"""
        raise NotImplementedError

    def support_async(self) -> bool:
        """Whether the loaded model supports asynchronous calls"""
        return False

    def get_generate_stream_function(self, model, model_path: str):
        """Get the generate stream function of the model"""
        raise NotImplementedError

    def get_async_generate_stream_function(self, model, model_path: str):
        """Get the asynchronous generate stream function of the model"""
        raise NotImplementedError

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> "Conversation":
        """Get the default conv template"""
        raise NotImplementedError

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
    ) -> Optional[str]:
        return None

    def get_prompt_with_template(
        self,
        params: Dict,
        messages: List[ModelMessage],
        model_name: str,
        model_path: str,
        model_context: Dict,
        prompt_template: str = None,
    ):
        conv = self.get_default_conv_template(model_name, model_path)

        if prompt_template:
            logger.info(f"Use prompt template {prompt_template} from config")
            conv = get_conv_template(prompt_template)
        if not conv or not messages:
            # Nothing to do
            logger.info(
                f"No conv from model_path {model_path} or no messages in params, {self}"
            )
            return None, None, None

        conv = conv.copy()
        system_messages = []
        user_messages = []
        ai_messages = []

        for message in messages:
            role, content = None, None
            if isinstance(message, ModelMessage):
                role = message.role
                content = message.content
            elif isinstance(message, dict):
                role = message["role"]
                content = message["content"]
            else:
                raise ValueError(f"Invalid message type: {message}")

            if role == ModelMessageRoleType.SYSTEM:
                # Support for multiple system messages
                system_messages.append(content)
            elif role == ModelMessageRoleType.HUMAN:
                # conv.append_message(conv.roles[0], content)
                user_messages.append(content)
            elif role == ModelMessageRoleType.AI:
                # conv.append_message(conv.roles[1], content)
                ai_messages.append(content)
            else:
                raise ValueError(f"Unknown role: {role}")

        can_use_systems: [] = []
        if system_messages:
            if len(system_messages) > 1:
                ##  Compatible with dbgpt complex scenarios, the last system will protect more complete information entered by the current user
                user_messages[-1] = system_messages[-1]
                can_use_systems = system_messages[:-1]
            else:
                can_use_systems = system_messages

        for i in range(len(user_messages)):
            conv.append_message(conv.roles[0], user_messages[i])
            if i < len(ai_messages):
                conv.append_message(conv.roles[1], ai_messages[i])

        if isinstance(conv, Conversation):
            conv.set_system_message("".join(can_use_systems))
        else:
            conv.update_system_message("".join(can_use_systems))

        # Add a blank message for the assistant.
        conv.append_message(conv.roles[1], None)
        new_prompt = conv.get_prompt()
        return new_prompt, conv.stop_str, conv.stop_token_ids

    def model_adaptation(
        self,
        params: Dict,
        model_name: str,
        model_path: str,
        tokenizer: Any,
        prompt_template: str = None,
    ) -> Tuple[Dict, Dict]:
        """Params adaptation"""
        messages = params.get("messages")
        # Some model scontext to dbgpt server
        model_context = {"prompt_echo_len_char": -1, "has_format_prompt": False}
        if messages:
            # Dict message to ModelMessage
            messages = [
                m if isinstance(m, ModelMessage) else ModelMessage(**m)
                for m in messages
            ]
            params["messages"] = messages

        new_prompt = self.get_str_prompt(params, messages, tokenizer, prompt_template)
        conv_stop_str, conv_stop_token_ids = None, None
        if not new_prompt:
            (
                new_prompt,
                conv_stop_str,
                conv_stop_token_ids,
            ) = self.get_prompt_with_template(
                params, messages, model_name, model_path, model_context, prompt_template
            )
            if not new_prompt:
                return params, model_context

        # Overwrite the original prompt
        # TODO remote bos token and eos token from tokenizer_config.json of model
        prompt_echo_len_char = len(new_prompt.replace("</s>", "").replace("<s>", ""))
        model_context["prompt_echo_len_char"] = prompt_echo_len_char
        model_context["echo"] = params.get("echo", True)
        model_context["has_format_prompt"] = True
        params["prompt"] = new_prompt

        custom_stop = params.get("stop")
        custom_stop_token_ids = params.get("stop_token_ids")

        # Prefer the value passed in from the input parameter
        params["stop"] = custom_stop or conv_stop_str
        params["stop_token_ids"] = custom_stop_token_ids or conv_stop_token_ids

        return params, model_context


class OldLLMModelAdaperWrapper(LLMModelAdaper):
    """Wrapping old adapter, which may be removed later"""

    def __init__(self, adapter: "OldBaseLLMAdaper", chat_adapter) -> None:
        self._adapter = adapter
        self._chat_adapter = chat_adapter

    def use_fast_tokenizer(self) -> bool:
        return self._adapter.use_fast_tokenizer()

    def model_type(self) -> str:
        return self._adapter.model_type()

    def model_param_class(self, model_type: str = None) -> ModelParameters:
        return self._adapter.model_param_class(model_type)

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> "Conversation":
        return self._chat_adapter.get_conv_template(model_path)

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        return self._adapter.loader(model_path, from_pretrained_kwargs)

    def get_generate_stream_function(self, model, model_path: str):
        return self._chat_adapter.get_generate_stream_func(model_path)

    def __str__(self) -> str:
        return "{}({}.{})".format(
            self.__class__.__name__,
            self._adapter.__class__.__module__,
            self._adapter.__class__.__name__,
        )


class FastChatLLMModelAdaperWrapper(LLMModelAdaper):
    """Wrapping fastchat adapter"""

    def __init__(self, adapter: "BaseModelAdapter") -> None:
        self._adapter = adapter

    def use_fast_tokenizer(self) -> bool:
        return self._adapter.use_fast_tokenizer

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        return self._adapter.load_model(model_path, from_pretrained_kwargs)

    def get_generate_stream_function(self, model: "TorchNNModule", model_path: str):
        if _IS_BENCHMARK:
            from dbgpt.util.benchmarks.llm.fastchat_benchmarks_inference import (
                generate_stream,
            )

            return generate_stream
        else:
            from fastchat.model.model_adapter import get_generate_stream_function

            return get_generate_stream_function(model, model_path)

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> "Conversation":
        return self._adapter.get_default_conv_template(model_path)

    def __str__(self) -> str:
        return "{}({}.{})".format(
            self.__class__.__name__,
            self._adapter.__class__.__module__,
            self._adapter.__class__.__name__,
        )


class NewHFChatModelAdapter(LLMModelAdaper):
    def load(self, model_path: str, from_pretrained_kwargs: dict):
        try:
            import transformers
            from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModel
        except ImportError as exc:
            raise ValueError(
                "Could not import depend python package "
                "Please install it with `pip install transformers`."
            ) from exc
        if not transformers.__version__ >= "4.34.0":
            raise ValueError(
                "Current model (Load by HFNewChatAdapter) require transformers.__version__>=4.34.0"
            )
        revision = from_pretrained_kwargs.get("revision", "main")
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                use_fast=self.use_fast_tokenizer,
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
    ) -> Optional[str]:
        from transformers import AutoTokenizer

        if not tokenizer:
            raise ValueError("tokenizer is is None")
        tokenizer: AutoTokenizer = tokenizer

        messages = ModelMessage.to_openai_messages(messages)
        str_prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return str_prompt


def get_conv_template(name: str) -> "Conversation":
    """Get a conversation template."""
    from fastchat.conversation import get_conv_template

    return get_conv_template(name)


@cache
def _auto_get_conv_template(model_name: str, model_path: str) -> "Conversation":
    try:
        adapter = get_llm_model_adapter(model_name, model_path, use_fastchat=True)
        return adapter.get_default_conv_template(model_name, model_path)
    except Exception:
        return None


@cache
def get_llm_model_adapter(
    model_name: str,
    model_path: str,
    use_fastchat: bool = True,
    use_fastchat_monkey_patch: bool = False,
    model_type: str = None,
) -> LLMModelAdaper:
    if model_type == ModelType.VLLM:
        logger.info("Current model type is vllm, return VLLMModelAdaperWrapper")
        return VLLMModelAdaperWrapper()

    use_new_hf_chat_models = any(m in model_name.lower() for m in _NEW_HF_CHAT_MODELS)
    if use_new_hf_chat_models:
        logger.info(f"Current model {model_name} use NewHFChatModelAdapter")
        return NewHFChatModelAdapter()

    must_use_old = any(m in model_name for m in _OLD_MODELS)
    if use_fastchat and not must_use_old:
        logger.info("Use fastcat adapter")
        adapter = _get_fastchat_model_adapter(
            model_name,
            model_path,
            _fastchat_get_adapter_monkey_patch,
            use_fastchat_monkey_patch=use_fastchat_monkey_patch,
        )
        return FastChatLLMModelAdaperWrapper(adapter)
    else:
        from dbgpt.model.adapter import (
            get_llm_model_adapter as _old_get_llm_model_adapter,
        )
        from dbgpt.app.chat_adapter import get_llm_chat_adapter

        logger.info("Use DB-GPT old adapter")
        return OldLLMModelAdaperWrapper(
            _old_get_llm_model_adapter(model_name, model_path),
            get_llm_chat_adapter(model_name, model_path),
        )


def _get_fastchat_model_adapter(
    model_name: str,
    model_path: str,
    caller: Callable[[str], None] = None,
    use_fastchat_monkey_patch: bool = False,
):
    from fastchat.model import model_adapter

    _bak_get_model_adapter = model_adapter.get_model_adapter
    try:
        if use_fastchat_monkey_patch:
            model_adapter.get_model_adapter = _fastchat_get_adapter_monkey_patch
        thread_local.model_name = model_name
        _remove_black_list_model_of_fastchat()
        if caller:
            return caller(model_path)
    finally:
        del thread_local.model_name
        model_adapter.get_model_adapter = _bak_get_model_adapter


def _fastchat_get_adapter_monkey_patch(model_path: str, model_name: str = None):
    if not model_name:
        if not hasattr(thread_local, "model_name"):
            raise RuntimeError("fastchat get adapter monkey path need model_name")
        model_name = thread_local.model_name
    from fastchat.model.model_adapter import model_adapters

    for adapter in model_adapters:
        if adapter.match(model_name):
            logger.info(
                f"Found llm model adapter with model name: {model_name}, {adapter}"
            )
            return adapter

    model_path_basename = (
        None if not model_path else os.path.basename(os.path.normpath(model_path))
    )
    for adapter in model_adapters:
        if model_path_basename and adapter.match(model_path_basename):
            logger.info(
                f"Found llm model adapter with model path: {model_path} and base name: {model_path_basename}, {adapter}"
            )
            return adapter

    for adapter in model_adapters:
        if model_path and adapter.match(model_path):
            logger.info(
                f"Found llm model adapter with model path: {model_path}, {adapter}"
            )
            return adapter

    raise ValueError(
        f"Invalid model adapter for model name {model_name} and model path {model_path}"
    )


@cache
def _remove_black_list_model_of_fastchat():
    from fastchat.model.model_adapter import model_adapters

    black_list_models = []
    for adapter in model_adapters:
        try:
            if (
                adapter.get_default_conv_template("/data/not_exist_model_path").name
                in _BLACK_LIST_MODLE_PROMPT
            ):
                black_list_models.append(adapter)
        except Exception:
            pass
    for adapter in black_list_models:
        model_adapters.remove(adapter)


def _dynamic_model_parser() -> Callable[[None], List[Type]]:
    from dbgpt.util.parameter_utils import _SimpleArgParser
    from dbgpt.model.parameter import (
        EmbeddingModelParameters,
        WorkerType,
        EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG,
    )

    pre_args = _SimpleArgParser("model_name", "model_path", "worker_type", "model_type")
    pre_args.parse()
    model_name = pre_args.get("model_name")
    model_path = pre_args.get("model_path")
    worker_type = pre_args.get("worker_type")
    model_type = pre_args.get("model_type")
    if model_name is None and model_type != ModelType.VLLM:
        return None
    if worker_type == WorkerType.TEXT2VEC:
        return [
            EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG.get(
                model_name, EmbeddingModelParameters
            )
        ]

    llm_adapter = get_llm_model_adapter(model_name, model_path, model_type=model_type)
    param_class = llm_adapter.model_param_class()
    return [param_class]


class VLLMModelAdaperWrapper(LLMModelAdaper):
    """Wrapping vllm engine"""

    def model_type(self) -> str:
        return ModelType.VLLM

    def model_param_class(self, model_type: str = None) -> ModelParameters:
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
        from vllm import AsyncLLMEngine
        from vllm.engine.arg_utils import AsyncEngineArgs
        import torch

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
    ) -> "Conversation":
        return _auto_get_conv_template(model_name, model_path)

    def __str__(self) -> str:
        return "{}.{}".format(self.__class__.__module__, self.__class__.__name__)


# Covering the configuration of fastcaht, we will regularly feedback the code here to fastchat.
# We also recommend that you modify it directly in the fastchat repository.

# source: https://huggingface.co/BAAI/AquilaChat2-34B/blob/4608b75855334b93329a771aee03869dbf7d88cc/predict.py#L212
register_conv_template(
    Conversation(
        name="aquila-legacy",
        system_message="A chat between a curious human and an artificial intelligence assistant. "
        "The assistant gives helpful, detailed, and polite answers to the human's questions.\n\n",
        roles=("### Human: ", "### Assistant: ", "System"),
        messages=(),
        offset=0,
        sep_style=SeparatorStyle.NO_COLON_TWO,
        sep="\n",
        sep2="</s>",
        stop_str=["</s>", "[UNK]"],
    ),
    override=True,
)
# source: https://huggingface.co/BAAI/AquilaChat2-34B/blob/4608b75855334b93329a771aee03869dbf7d88cc/predict.py#L227
register_conv_template(
    Conversation(
        name="aquila",
        system_message="A chat between a curious human and an artificial intelligence assistant. "
        "The assistant gives helpful, detailed, and polite answers to the human's questions.",
        roles=("Human", "Assistant", "System"),
        messages=(),
        offset=0,
        sep_style=SeparatorStyle.ADD_COLON_TWO,
        sep="###",
        sep2="</s>",
        stop_str=["</s>", "[UNK]"],
    ),
    override=True,
)
# source: https://huggingface.co/BAAI/AquilaChat2-34B/blob/4608b75855334b93329a771aee03869dbf7d88cc/predict.py#L242
register_conv_template(
    Conversation(
        name="aquila-v1",
        roles=("<|startofpiece|>", "<|endofpiece|>", ""),
        messages=(),
        offset=0,
        sep_style=SeparatorStyle.NO_COLON_TWO,
        sep="",
        sep2="</s>",
        stop_str=["</s>", "<|endoftext|>"],
    ),
    override=True,
)
