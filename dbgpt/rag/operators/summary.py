from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel.task.base import IN
from dbgpt.serve.rag.assembler.summary import SummaryAssembler
from dbgpt.serve.rag.operators.base import AssemblerOperator


class SummaryAssemblerOperator(AssemblerOperator[Any, Any]):
    def __init__(
        self,
        llm_client: Optional[LLMClient],
        model_name: Optional[str] = "gpt-3.5-turbo",
        language: Optional[str] = "en",
        max_iteration_with_llm: Optional[int] = 5,
        concurrency_limit_with_llm: Optional[int] = 3,
        **kwargs
    ):
        """
        Init the summary assemble operator.
        Args:
              llm_client: (Optional[LLMClient]) The LLM client.
              model_name: (Optional[str]) The model name.
              language: (Optional[str]) The prompt language.
              max_iteration_with_llm: (Optional[int]) The max iteration with llm.
              concurrency_limit_with_llm: (Optional[int]) The concurrency limit with llm.
        """
        super().__init__(**kwargs)
        self._llm_client = llm_client
        self._model_name = model_name
        self._language = language
        self._max_iteration_with_llm = max_iteration_with_llm
        self._concurrency_limit_with_llm = concurrency_limit_with_llm

    async def map(self, knowledge: IN) -> Any:
        """Assemble the summary."""
        assembler = SummaryAssembler.load_from_knowledge(
            knowledge=knowledge,
            llm_client=self._llm_client,
            model_name=self._model_name,
            language=self._language,
            max_iteration_with_llm=self._max_iteration_with_llm,
            concurrency_limit_with_llm=self._concurrency_limit_with_llm,
        )
        return await assembler.generate_summary()

    def assemble(self, knowledge: IN) -> Any:
        """assemble knowledge for input value."""
        pass
