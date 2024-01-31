import json
import logging
from typing import Dict, Optional

from dbgpt.agent.agents.llm.llm import LLMStrategyType

from ..llm import LLMStrategy

logger = logging.getLogger(__name__)


class LLMStrategyPriority(LLMStrategy):
    @property
    def type(self) -> LLMStrategyType:
        return LLMStrategyType.Priority

    async def next_llm(self, excluded_models: Optional[List[str]] = None) -> str:
        try:
            all_models = self._llm_client.models()
            priority: List[str] = json.loads(self._context)
            can_uses = self._excluded_models(all_models, priority, excluded_models)
            if can_uses and len(can_uses) > 0:
                return can_uses[0].model
            else:
                raise ValueError("No model service available!")

        except Exception as e:
            logger.error(f"{self.type} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")
