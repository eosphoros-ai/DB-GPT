"""Priority strategy for LLM."""

import json
import logging
from typing import List, Optional

from ..llm import LLMStrategy, LLMStrategyType, register_llm_strategy_cls

logger = logging.getLogger(__name__)


class LLMStrategyPriority(LLMStrategy):
    """Priority strategy for llm model service."""

    @property
    def type(self) -> LLMStrategyType:
        """Return the strategy type."""
        return LLMStrategyType.Priority

    async def next_llm(self, excluded_models: Optional[List[str]] = None) -> str:
        """Return next available llm model name."""
        try:
            all_models = await self._llm_client.models()
            all_model_names = [item.model for item in all_models]

            if not self._context:
                raise ValueError("No context provided for priority strategy!")
            if isinstance(self._context, str):
                priority = json.loads(self._context)
            else:
                priority = self._context
            logger.info(f"Use {self.type} llm strategy! value:{self._context}")
            can_uses = self._excluded_models(all_model_names, priority, excluded_models)

            if can_uses and len(can_uses) > 0:
                return can_uses[0]
            else:
                raise ValueError("No model service available!")
        except Exception as e:
            logger.error(f"{self.type} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")


register_llm_strategy_cls(LLMStrategyType.Priority, LLMStrategyPriority)
