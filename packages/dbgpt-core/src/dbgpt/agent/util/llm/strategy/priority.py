"""Priority strategy for LLM."""

import json
import logging
from typing import List, Optional

from ..llm import LLMStrategy, LLMStrategyType

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
            if not excluded_models:
                excluded_models = []
            all_models = await self._llm_client.models()
            if not self._context:
                raise ValueError("No context provided for priority strategy!")
            priority: List[str] = json.loads(self._context)
            can_uses = self._excluded_models(all_models, excluded_models, priority)
            if can_uses and len(can_uses) > 0:
                return can_uses[0].model
            else:
                raise ValueError("No model service available!")

        except Exception as e:
            logger.error(f"{self.type} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")
