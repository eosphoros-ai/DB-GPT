from __future__ import annotations

import logging
import os
import threading
from functools import cache
from typing import List, Optional, Type

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import LLMModelAdapter, get_model_adapter
from dbgpt.model.adapter.template import ConversationAdapter, ConversationAdapterFactory
from dbgpt.model.base import ModelType

logger = logging.getLogger(__name__)

thread_local = threading.local()
_IS_BENCHMARK = os.getenv("DB_GPT_MODEL_BENCHMARK", "False").lower() == "true"


@cache
def get_llm_model_adapter(
    model_name: str,
    model_path: Optional[str] = None,
    use_fastchat: bool = True,
    use_fastchat_monkey_patch: bool = False,
    model_type: str = None,
) -> LLMModelAdapter:
    conv_factory = DefaultConversationAdapterFactory()

    new_model_adapter = get_model_adapter(
        model_type, model_name, model_path, conv_factory
    )
    if new_model_adapter:
        logger.info(f"Current model {model_name} use new adapter {new_model_adapter}")
        return new_model_adapter

    result_adapter: Optional[LLMModelAdapter] = None
    if use_fastchat:
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


def _dynamic_model_parser() -> Optional[List[Type[LLMDeployModelParameters]]]:
    """Dynamic model parser, parse the model parameters from the command line arguments.

    Returns:
        Optional[List[Type[BaseModelParameters]]]: The model parameters class list.
    """
    from dbgpt.model.adapter.base import get_embedding_adapter
    from dbgpt.model.parameter import WorkerType
    from dbgpt.util.parameter_utils import _SimpleArgParser

    pre_args = _SimpleArgParser("model_name", "model_path", "worker_type", "model_type")
    pre_args.parse()
    model_name = pre_args.get("model_name")
    model_path = pre_args.get("model_path")
    worker_type = pre_args.get("worker_type")
    model_type = pre_args.get("model_type")
    if worker_type == WorkerType.TEXT2VEC:
        adapter = get_embedding_adapter(
            model_type,
            is_rerank=False,
            model_name=model_name,
            model_path=model_path,
        )
        return [adapter.model_param_class()]
    if model_name is None and model_type != ModelType.VLLM:
        return None
    llm_adapter = get_llm_model_adapter(model_name, model_path, model_type=model_type)
    param_class = llm_adapter.model_param_class()
    return [param_class]
