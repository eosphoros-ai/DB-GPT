"""LLM module."""

import logging
from abc import ABC
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import LLMClient, ModelRequest

logger = logging.getLogger(__name__)


def _build_model_request(input_value: Dict) -> ModelRequest:
    """Build model request from input value.

    Args:
        input_value(str or dict): input value

    Returns:
        ModelRequest: model request, pass to llm client
    """
    parm = {
        "model": input_value.get("model"),
        "messages": input_value.get("messages"),
        "temperature": input_value.get("temperature", None),
        "max_new_tokens": input_value.get("max_new_tokens", None),
        "stop": input_value.get("stop", None),
        "stop_token_ids": input_value.get("stop_token_ids", None),
        "context_len": input_value.get("context_len", None),
        "echo": input_value.get("echo", None),
        "span_id": input_value.get("span_id", None),
    }

    return ModelRequest(**parm)


class LLMStrategyType(Enum):
    """LLM strategy type."""

    def __new__(cls, value, name_cn, description, description_en):
        """Overide new."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj.name_cn = name_cn
        obj.description = description
        obj.description_en = description_en
        return obj

    Priority = ("priority", "优先级", "根据优先级使用模型", "Use LLM based on priority")
    Auto = ("auto", "自动", "自动选择的策略", "Automatically select LLM strategies")
    Default = (
        "default",
        "默认",
        "默认的策略",
        "Use the LLM specified by the system default",
    )

    def to_dict(self):
        """To dict."""
        return {
            "name": self.name,
            "name_cn": self.name_cn,
            "value": self.value,
            "description": self.description,
            "description_en": self.description_en,
        }


class LLMStrategy(ABC):
    def __init__(self, llm_client: LLMClient, context: Optional[str] = None):
        self._llm_client = llm_client
        self._context = context

    @property
    def type(self) -> LLMStrategyType:
        return LLMStrategyType.Default

    def _excluded_models(
        self,
        all_models: List[str],
        order_llms: Optional[List[str]] = None,
        excluded_models: Optional[List[str]] = None,
    ):
        if not order_llms:
            order_llms = []
        if not excluded_models:
            excluded_models = []
        can_uses = []
        if order_llms and len(order_llms) > 0:
            for llm_name in order_llms:
                if llm_name in all_models and (
                    not excluded_models or llm_name not in excluded_models
                ):
                    can_uses.append(llm_name)
        else:
            for llm_name in all_models:
                if not excluded_models or llm_name not in excluded_models:
                    can_uses.append(llm_name)

        return can_uses

    async def next_llm(self, excluded_models: Optional[List[str]] = None):
        """Return next available llm model name.

        Args:
            excluded_models(List[str]): excluded models

        Returns:
            str: Next available llm model name
        """
        if not excluded_models:
            excluded_models = []
        try:
            all_models = await self._llm_client.models()
            all_model_names = [item.model for item in all_models]

            can_uses = self._excluded_models(all_model_names, None, excluded_models)
            if can_uses and len(can_uses) > 0:
                return can_uses[0]
            else:
                raise ValueError("No model service available!")

        except Exception as e:
            logger.error(f"{self.type} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")


### Model selection strategy registration, built-in strategy registration by default
llm_strategies: Dict[LLMStrategyType, List[Type[LLMStrategy]]] = defaultdict(
    Type[LLMStrategy]
)


def register_llm_strategy_cls(
    llm_strategy_type: LLMStrategyType, strategy: Type[LLMStrategy]
):
    """Register llm strategy."""
    llm_strategies[llm_strategy_type] = strategy


def get_llm_strategy_cls(
    llm_strategy_type: LLMStrategyType,
) -> Optional[Type[LLMStrategy]]:
    return llm_strategies.get(llm_strategy_type, None)


register_llm_strategy_cls(LLMStrategyType.Default, LLMStrategy)


class LLMConfig(BaseModel):
    """LLM configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_client: Optional[LLMClient] = Field(default_factory=LLMClient)
    llm_strategy: LLMStrategyType = Field(default=LLMStrategyType.Default)
    strategy_context: Optional[Any] = None
