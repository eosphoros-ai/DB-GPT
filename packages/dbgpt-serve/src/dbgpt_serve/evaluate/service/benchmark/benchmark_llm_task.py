import logging
from typing import Optional, Union

from dbgpt.core import HumanPromptTemplate, LLMClient, ModelMessage, ModelRequest
from dbgpt_serve.evaluate.service.benchmark.models import ReasoningResponse
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import (
    get_benchmark_manager,
)

logger = logging.getLogger(__name__)


class BenchmarkLLMTask:
    """BenchmarkLLMTask class."""

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: Optional[str],
        prompt_template: Optional[str] = None,
    ):
        """Initialize the BenchmarkLLMTask"""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template
        db_connector = get_benchmark_manager().get_connector()
        if db_connector:
            self.dialect = db_connector.dialect

    async def invoke_llm(
        self, prompt: Optional[str] = None, **kwargs
    ) -> Union[ReasoningResponse, None]:
        """
        Invoke by LLM.

        Args:
            prompt (Optional[str]): The prompt to use for the LLM.
            **kwargs: Keyword arguments for variable replacement in prompt template.
                     For example: text="user input", question="What is AI?", etc.
        """
        return await self._invoke_task(prompt, **kwargs)

    async def _invoke_task(
        self, prompt: Optional[str], **kwargs
    ) -> Union[ReasoningResponse, None]:
        if self._prompt_template:
            prompt = self._prompt_template
        template = HumanPromptTemplate.from_template(
            template=prompt, template_is_strict=False
        )
        if self.dialect and "dialect" not in kwargs:
            kwargs["dialect"] = self.dialect

        messages = template.format_messages(**kwargs)

        # use default model if needed
        if not self._model_name:
            models = await self._llm_client.models()
            if not models:
                raise Exception("No models available")
            self._model_name = models[0].model
            logger.info(f"Using model {self._model_name} to extract")

        model_messages = ModelMessage.from_base_messages(messages)
        request_kwargs = {}
        # Map kwargs to ModelRequest parameters if provided
        if "temperature" in kwargs:
            request_kwargs["temperature"] = kwargs.get("temperature")
        if "max_tokens" in kwargs:
            # ModelRequest uses max_new_tokens
            request_kwargs["max_new_tokens"] = kwargs.get("max_tokens")

        request = ModelRequest(
            model=self._model_name, messages=model_messages, **request_kwargs
        )
        response = await self._llm_client.generate(request=request)

        if not response:
            logger.error("[benchmarkLLMTask] request llm failed, response is None")
            return None

        if not response.success:
            code = str(response.error_code)
            reason = response.text
            logger.error(f"[benchmarkLLMTask] request llm failed ({code}) {reason}")
            return None

        if response.has_text:
            cot_tokens = 0
            if response.usage and isinstance(response.usage, dict):
                cot_tokens = response.usage.get("total_tokens", 0)

            return ReasoningResponse(
                cot_tokens=cot_tokens,
                think=response.thinking_text if response.has_thinking else None,
                content=self._get_answer(response.text),
            )
        else:
            return None

    def _get_answer(self, output: str) -> Optional[str]:
        answer = None

        if "</think>" in output:
            parts = output.split("</think>")
            if len(parts) > 1:
                answer = parts[1]
        elif "<answer>" in output:
            parts = output.split("<answer>")
            if len(parts) > 1:
                answer = parts[1]
        else:
            answer = output
        return answer
