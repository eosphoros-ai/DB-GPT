"""TripletExtractor class."""
import logging
from abc import ABC, abstractmethod
from typing import List

from dbgpt.core import HumanPromptTemplate, LLMClient, ModelMessage, ModelRequest
from dbgpt.rag.transformer.base import ExtractorBase

logger = logging.getLogger(__name__)


class LLMExtractor(ExtractorBase, ABC):
    """LLMExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str, prompt_template: str):
        """Initialize the LLMExtractor with a LLM client and a specific model."""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template

    async def extract(self, text: str, limit: int = None) -> List:
        """Extract keywords from text using the configured model."""
        template = HumanPromptTemplate.from_template(self._prompt_template)
        messages = template.format_messages(text=text)

        model_messages = ModelMessage.from_base_messages(messages)
        request = ModelRequest(model=self._model_name, messages=model_messages)
        response = await self._llm_client.generate(request=request)

        if not response.success:
            code = str(response.error_code)
            reason = response.text
            logger.error(f"request llm failed ({code}) {reason}")
            return []

        if limit and limit < 1:
            ValueError("optional argument limit >= 1")
        return self._parse_response(response.text, limit)

    @abstractmethod
    def _parse_response(self, text: str, limit: int) -> List:
        """Parse llm response."""
