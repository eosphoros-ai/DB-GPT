"""LLMTranslator class."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from dbgpt.core import HumanPromptTemplate, LLMClient, ModelMessage, ModelRequest
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
        return await self._translate(text, None, limit)

    @abstractmethod
    async def _translate(
        self, text: str, history: str = None, limit: Optional[int] = None
    ) -> Dict:
        """Inner translate by LLM."""

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""

    @abstractmethod
    def _parse_response(self, text: str, limit: Optional[int] = None) -> Dict:
        """Parse llm response."""
