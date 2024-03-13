import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field

from dbgpt.core import LLMClient
from dbgpt.core.interface.llm import ModelMetadata, ModelRequest

logger = logging.getLogger(__name__)


def _build_model_request(
    input_value: Union[Dict, str], model: Optional[str] = None
) -> ModelRequest:
    """Build model request from input value.

    Args:
        input_value(str or dict): input value
        model(Optional[str]): model name

    Returns:
        ModelRequest: model request, pass to llm client
    """
    if isinstance(input_value, str):
        return ModelRequest._build(model, input_value)
    elif isinstance(input_value, dict):
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
    else:
        raise ValueError("Build model request input Error!")


class LLMStrategyType(Enum):
    Priority = "priority"
    Auto = "auto"
    Default = "default"


class LLMStrategy(ABC):
    def __init__(self, llm_client: LLMClient, context: Optional[str] = None):
        self._llm_client = llm_client
        self._context = context

    @property
    def type(self) -> LLMStrategyType:
        return LLMStrategyType.Default

    def _excluded_models(
        self,
        all_models: Optional[list],
        need_uses: Optional[list] = [],
        excluded_models: Optional[list] = [],
    ):
        can_uses = []
        for item in all_models:
            if item.model in need_uses and item.model not in excluded_models:
                can_uses.append(item)
        return can_uses

    async def next_llm(self, excluded_models: Optional[List[str]] = None):
        """
        Args:
            excluded_model:

        Returns:
        """
        try:
            all_models = self._llm_client.models()
            priority: List[str] = json.loads(self._context)
            available_llms = self._excluded_models(all_models, None, excluded_models)
            if available_llms and len(available_llms) > 0:
                return available_llms[0].model
            else:
                raise ValueError("No model service available!")

        except Exception as e:
            logger.error(f"{self.type} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")


llm_strategys = defaultdict(list)


def register_llm_strategy(type: LLMStrategyType, strategy: Type[LLMStrategy]):
    llm_strategys[type] = strategy


class LLMConfig(BaseModel):
    llm_client: Optional[LLMClient] = Field(default_factory=LLMClient)
    llm_strategy: LLMStrategyType = Field(default=LLMStrategyType.Default)
    strategy_context: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True
