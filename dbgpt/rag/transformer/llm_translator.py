"""LLMTranslator class."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from dbgpt.core import LLMClient, ModelMessage, ModelRequest
from dbgpt.rag.transformer.base import TranslatorBase

logger = logging.getLogger(__name__)


class LLMTranslator(TranslatorBase, ABC):
    """LLMTranslator class."""

    def __init__(self, llm_client: LLMClient, model_name: str, prompt_template: str):
        """Initialize the LLMExtractor."""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template

    async def translate(self, text: str, limit: Optional[int] = None) -> Dict:
        """Translate by LLM."""
        messages = self._format_messages(text)
        return await self._translate(messages, limit)

    async def _translate(self, messages: str, limit: Optional[int] = None) -> Dict:
        """Inner translate by LLM."""
        # use default model if needed
        if not self._model_name:
            models = await self._llm_client.models()
            if not models:
                raise Exception("No models available")
            self._model_name = models[0].model
            logger.info(f"Using model {self._model_name} to extract")

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

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""

    @abstractmethod
    def _format_messages(self, text: str, history: str = None) -> str:
        """Parse llm response."""

    @abstractmethod
    def _parse_response(self, text: str, limit: Optional[int] = None) -> Dict:
        """Parse llm response."""
