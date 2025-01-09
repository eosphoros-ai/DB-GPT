"""TripletExtractor class."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from dbgpt.core import HumanPromptTemplate, LLMClient, ModelMessage, ModelRequest
from dbgpt.rag.transformer.base import ExtractorBase

logger = logging.getLogger(__name__)


class LLMExtractor(ExtractorBase, ABC):
    """LLMExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str, prompt_template: str):
        """Initialize the LLMExtractor."""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template

    async def extract(self, text: str, limit: Optional[int] = None) -> List:
        """Extract by LLM."""
        return await self._extract(text, None, limit)

    async def batch_extract(
        self,
        texts: List[str],
        batch_size: int = 1,
        limit: Optional[int] = None,
    ) -> List:
        """Batch extract by LLM."""
        if batch_size < 1:
            raise ValueError("batch_size >= 1")

        results = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]

            # Create tasks for current batch
            extraction_tasks = [
                self._extract(text, None, limit) for text in batch_texts
            ]

            # Execute batch concurrently and wait for all to complete
            batch_results = await asyncio.gather(*extraction_tasks)
            results.extend(batch_results)

        return results

    async def _extract(
        self, text: str, history: str = None, limit: Optional[int] = None
    ) -> List:
        """Inner extract by LLM."""
        template = HumanPromptTemplate.from_template(self._prompt_template)

        messages = (
            template.format_messages(text=text, history=history)
            if history is not None
            else template.format_messages(text=text)
        )

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
    def _parse_response(self, text: str, limit: Optional[int] = None) -> List:
        """Parse llm response."""
