import logging
from typing import Optional, Union

from dbgpt.core import HumanPromptTemplate, LLMClient, ModelMessage, ModelRequest
from dbgpt_serve.evaluate.service.benchmark.models import ReasoningResponse

logger = logging.getLogger(__name__)


class BenchmarkLLMTask:
    """BenchmarkLLMTask class."""

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: Optional[str],
        prompt_template: Optional[str],
    ):
        """Initialize the BenchmarkLLMTask"""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template

    async def invoke_llm(
        self, text: Optional[str] = None, prompt: Optional[str] = None
    ) -> Union[ReasoningResponse, None]:
        """Extract by LLM."""
        return await self._invoke_task(text, prompt)

    async def _invoke_task(
        self, text: Optional[str], prompt: Optional[str]
    ) -> Union[ReasoningResponse, None]:
        if self._prompt_template:
            prompt = self._prompt_template
        template = HumanPromptTemplate.from_template(
            template=prompt, template_is_strict=False
        )
        messages = template.format_messages(text=text)

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
            logger.error(f"[benchmarkLLMTask] request llm failed ({code}) {reason}")
            return None

        if response.has_text:
            return ReasoningResponse(content=self._get_answer(response.text))
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
