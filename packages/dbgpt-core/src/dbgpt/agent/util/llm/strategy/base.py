from enum import Enum
from typing import Any, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import LLMClient


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


class LLMConfig(BaseModel):
    """LLM configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_client: Optional[LLMClient] = Field(default_factory=LLMClient)
    llm_strategy: LLMStrategyType = Field(default=LLMStrategyType.Default)
    strategy_context: Optional[Any] = None
