"""Adapter for fastchat

You can import fastchat only in this file, so that the user does not need to install
fastchat if he does not use it.
"""

import logging
import os
import threading
from functools import cache
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.model.adapter.template import ConversationAdapter, PromptType

try:
    from fastchat.conversation import (
        Conversation,
        SeparatorStyle,
        register_conv_template,
    )
except ImportError as exc:
    raise ValueError(
        "Could not import python package: fschat "
        "Please install fastchat by command `pip install fschat` "
    ) from exc


if TYPE_CHECKING:
    from fastchat.model.model_adapter import BaseModelAdapter
    from torch.nn import Module as TorchNNModule

logger = logging.getLogger(__name__)

thread_local = threading.local()
_IS_BENCHMARK = os.getenv("DB_GPT_MODEL_BENCHMARK", "False").lower() == "true"

# If some model is not in the blacklist, but it still affects the loading of DB-GPT,
# you can add it to the blacklist.
__BLACK_LIST_MODEL_PROMPT = []


class FschatConversationAdapter(ConversationAdapter):
    """The conversation adapter for fschat."""

    def __init__(self, conv: Conversation):
        self._conv = conv

    @property
    def prompt_type(self) -> PromptType:
        return PromptType.FSCHAT

    @property
    def roles(self) -> Tuple[str]:
        return self._conv.roles

    @property
    def sep(self) -> Optional[str]:
        return self._conv.sep

    @property
    def stop_str(self) -> str:
        return self._conv.stop_str

    @property
    def stop_token_ids(self) -> Optional[List[int]]:
        return self._conv.stop_token_ids

    def get_prompt(self) -> str:
        """Get the prompt string."""
        return self._conv.get_prompt()

    def set_system_message(self, system_message: str) -> None:
        """Set the system message."""
        self._conv.set_system_message(system_message)

    def append_message(self, role: str, message: str) -> None:
        """Append a new message.

        Args:
            role (str): The role of the message.
            message (str): The message content.
        """
        self._conv.append_message(role, message)

    def update_last_message(self, message: str) -> None:
        """Update the last output.

        The last message is typically set to be None when constructing the prompt,
        so we need to update it in-place after getting the response from a model.

        Args:
            message (str): The message content.
        """
        self._conv.update_last_message(message)

    def copy(self) -> "ConversationAdapter":
        """Copy the conversation."""
        return FschatConversationAdapter(self._conv.copy())


class FastChatLLMModelAdapterWrapper(LLMModelAdapter):
    """Wrapping fastchat adapter"""

    def __init__(self, adapter: "BaseModelAdapter") -> None:
        self._adapter = adapter

    def new_adapter(self, **kwargs) -> "LLMModelAdapter":
        new_obj = super().new_adapter(**kwargs)
        new_obj._adapter = self._adapter
        return new_obj

    def use_fast_tokenizer(self) -> bool:
        return self._adapter.use_fast_tokenizer

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        return self._adapter.load_model(model_path, from_pretrained_kwargs)

    def get_generate_stream_function(
        self, model: "TorchNNModule", deploy_model_params: LLMDeployModelParameters
    ):
        if _IS_BENCHMARK:
            from dbgpt.util.benchmarks.llm.fastchat_benchmarks_inference import (
                generate_stream,
            )

            return generate_stream
        else:
            from fastchat.model.model_adapter import get_generate_stream_function

            model_path = deploy_model_params.real_model_path
            return get_generate_stream_function(model, model_path)

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        conv_template = self._adapter.get_default_conv_template(model_path)
        return FschatConversationAdapter(conv_template) if conv_template else None

    def __str__(self) -> str:
        return "{}({}.{})".format(
            self.__class__.__name__,
            self._adapter.__class__.__module__,
            self._adapter.__class__.__name__,
        )


def _get_fastchat_model_adapter(
    model_name: str,
    model_path: Optional[str] = None,
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
                f"Found llm model adapter with model path: {model_path} and base name: "
                f"{model_path_basename}, {adapter}"
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
                in __BLACK_LIST_MODEL_PROMPT
            ):
                black_list_models.append(adapter)
        except Exception:
            pass
    for adapter in black_list_models:
        model_adapters.remove(adapter)


# Covering the configuration of fastcaht, we will regularly feedback the code here to
# fastchat.
# We also recommend that you modify it directly in the fastchat repository.

# source: https://huggingface.co/BAAI/AquilaChat2-34B/blob/4608b75855334b93329a771aee03869dbf7d88cc/predict.py#L212 # noqa
register_conv_template(
    Conversation(
        name="aquila-legacy",
        system_message="A chat between a curious human and an artificial intelligence "
        "assistant. The assistant gives helpful, detailed, and polite answers to the "
        "human's questions.\n\n",
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
# source: https://huggingface.co/BAAI/AquilaChat2-34B/blob/4608b75855334b93329a771aee03869dbf7d88cc/predict.py#L227 # noqa
register_conv_template(
    Conversation(
        name="aquila",
        system_message="A chat between a curious human and an artificial intelligence "
        "assistant. The assistant gives helpful, detailed, and polite answers to the "
        "human's questions.",
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
# source: https://huggingface.co/BAAI/AquilaChat2-34B/blob/4608b75855334b93329a771aee03869dbf7d88cc/predict.py#L242 # noqa
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
