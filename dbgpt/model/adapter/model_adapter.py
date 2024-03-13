from __future__ import annotations

import logging
import os
import threading
from functools import cache
from typing import List, Optional, Type

from dbgpt.model.adapter.base import LLMModelAdapter, get_model_adapter
from dbgpt.model.adapter.template import ConversationAdapter, ConversationAdapterFactory
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import BaseModelParameters

logger = logging.getLogger(__name__)

thread_local = threading.local()
_IS_BENCHMARK = os.getenv("DB_GPT_MODEL_BENCHMARK", "False").lower() == "true"


_OLD_MODELS = [
    "llama-cpp",
    # "proxyllm",
    "gptj-6b",
    "codellama-13b-sql-sft",
    "codellama-7b",
    "codellama-7b-sql-sft",
    "codellama-13b",
]


@cache
def get_llm_model_adapter(
    model_name: str,
    model_path: str,
    use_fastchat: bool = True,
    use_fastchat_monkey_patch: bool = False,
    model_type: str = None,
) -> LLMModelAdapter:
    conv_factory = DefaultConversationAdapterFactory()
    if model_type == ModelType.VLLM:
        logger.info("Current model type is vllm, return VLLMModelAdapterWrapper")
        from dbgpt.model.adapter.vllm_adapter import VLLMModelAdapterWrapper

        return VLLMModelAdapterWrapper(conv_factory)

    # Import NewHFChatModelAdapter for it can be registered
    from dbgpt.model.adapter.hf_adapter import NewHFChatModelAdapter
    from dbgpt.model.adapter.proxy_adapter import ProxyLLMModelAdapter

    new_model_adapter = get_model_adapter(
        model_type, model_name, model_path, conv_factory
    )
    if new_model_adapter:
        logger.info(f"Current model {model_name} use new adapter {new_model_adapter}")
        return new_model_adapter

    must_use_old = any(m in model_name for m in _OLD_MODELS)
    result_adapter: Optional[LLMModelAdapter] = None
    if use_fastchat and not must_use_old:
        logger.info("Use fastcat adapter")
        from dbgpt.model.adapter.fschat_adapter import (
            FastChatLLMModelAdapterWrapper,
            _fastchat_get_adapter_monkey_patch,
            _get_fastchat_model_adapter,
        )

        adapter = _get_fastchat_model_adapter(
            model_name,
            model_path,
            _fastchat_get_adapter_monkey_patch,
            use_fastchat_monkey_patch=use_fastchat_monkey_patch,
        )
        if adapter:
            result_adapter = FastChatLLMModelAdapterWrapper(adapter)

    else:
        from dbgpt.app.chat_adapter import get_llm_chat_adapter
        from dbgpt.model.adapter.old_adapter import OldLLMModelAdapterWrapper
        from dbgpt.model.adapter.old_adapter import (
            get_llm_model_adapter as _old_get_llm_model_adapter,
        )

        logger.info("Use DB-GPT old adapter")
        result_adapter = OldLLMModelAdapterWrapper(
            _old_get_llm_model_adapter(model_name, model_path),
            get_llm_chat_adapter(model_name, model_path),
        )
    if result_adapter:
        result_adapter.model_name = model_name
        result_adapter.model_path = model_path
        result_adapter.conv_factory = conv_factory
        return result_adapter
    else:
        raise ValueError(f"Can not find adapter for model {model_name}")


@cache
def _auto_get_conv_template(
    model_name: str, model_path: str
) -> Optional[ConversationAdapter]:
    """Auto get the conversation template.

    Args:
        model_name (str): The name of the model.
        model_path (str): The path of the model.

    Returns:
        Optional[ConversationAdapter]: The conversation template.
    """
    try:
        adapter = get_llm_model_adapter(model_name, model_path, use_fastchat=True)
        return adapter.get_default_conv_template(model_name, model_path)
    except Exception as e:
        logger.debug(f"Failed to get conv template for {model_name} {model_path}: {e}")
        return None


class DefaultConversationAdapterFactory(ConversationAdapterFactory):
    def get_by_model(self, model_name: str, model_path: str) -> ConversationAdapter:
        """Get a conversation adapter by model.

        Args:
            model_name (str): The name of the model.
            model_path (str): The path of the model.
        Returns:
            ConversationAdapter: The conversation adapter.
        """
        return _auto_get_conv_template(model_name, model_path)


def _dynamic_model_parser() -> Optional[List[Type[BaseModelParameters]]]:
    """Dynamic model parser, parse the model parameters from the command line arguments.

    Returns:
        Optional[List[Type[BaseModelParameters]]]: The model parameters class list.
    """
    from dbgpt.model.parameter import (
        EMBEDDING_NAME_TO_PARAMETER_CLASS_CONFIG,
        EmbeddingModelParameters,
        WorkerType,
    )
    from dbgpt.util.parameter_utils import _SimpleArgParser

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
