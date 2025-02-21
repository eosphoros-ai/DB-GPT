"""LLM module."""

import logging
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import LLMClient, ModelMetadata, ModelRequest

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


class LLMStrategy:
    """LLM strategy base class."""

    def __init__(self, llm_client: LLMClient, context: Optional[str] = None):
        """Create an LLMStrategy instance."""
        self._llm_client = llm_client
        self._context = context

    @property
    def type(self) -> LLMStrategyType:
        """Return the strategy type."""
        return LLMStrategyType.Default

    def _excluded_models(
        self,
        all_models: List[ModelMetadata],
        excluded_models: List[str],
        need_uses: Optional[List[str]] = None,
    ):
        if not need_uses:
            need_uses = []
        can_uses = []
        for item in all_models:
            if item.model in need_uses and item.model not in excluded_models:
                can_uses.append(item)
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
            available_llms = self._excluded_models(all_models, excluded_models, None)
            if available_llms and len(available_llms) > 0:
                return available_llms[0].model
            else:
                raise ValueError("No model service available!")

        except Exception as e:
            logger.error(f"{self.type} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")


llm_strategies: Dict[LLMStrategyType, List[Type[LLMStrategy]]] = defaultdict(list)


def register_llm_strategy(
    llm_strategy_type: LLMStrategyType, strategy: Type[LLMStrategy]
):
    """Register llm strategy."""
    llm_strategies[llm_strategy_type].append(strategy)


class LLMConfig(BaseModel):
    """LLM configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_client: Optional[LLMClient] = Field(default_factory=LLMClient)
    llm_strategy: LLMStrategyType = Field(default=LLMStrategyType.Default)
    strategy_context: Optional[Any] = None
