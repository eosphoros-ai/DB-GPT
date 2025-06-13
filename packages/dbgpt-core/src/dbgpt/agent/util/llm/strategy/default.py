import logging
from abc import ABC
from typing import List, Optional

from dbgpt.core import LLMClient

from .base import LLMStrategyType

logger = logging.getLogger(__name__)


class LLMStrategy(ABC):
    def __init__(self, llm_client: LLMClient, context: Optional[str] = None):
        self._llm_client = llm_client
        self._context = context

    @classmethod
    def type(cls) -> LLMStrategyType:
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
