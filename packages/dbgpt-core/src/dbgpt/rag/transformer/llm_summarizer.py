"""LLMSummarizer class."""

import logging
from abc import ABC

from dbgpt.core import HumanPromptTemplate, LLMClient, ModelMessage, ModelRequest
from dbgpt.rag.transformer.base import SummarizerBase

logger = logging.getLogger(__name__)


class LLMSummarizer(SummarizerBase, ABC):
    """LLMSummarizer class."""

    def __init__(self, llm_client: LLMClient, model_name: str, prompt_template: str):
        """Initialize the LLMSummarizer."""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template

    async def summarize(self, **args) -> str:
        """Summarize by LLM."""
        template = HumanPromptTemplate.from_template(self._prompt_template)
        messages = template.format_messages(**args)

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

        return response.text

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""
