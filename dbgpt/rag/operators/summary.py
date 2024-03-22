"""The summary operator."""

from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.rag.assembler.summary import SummaryAssembler
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.operators.assembler import AssemblerOperator


class SummaryAssemblerOperator(AssemblerOperator[Any, Any]):
    """The summary assembler operator."""

    metadata = ViewMetadata(
        label="Summary Operator",
        name="summary_assembler_operator",
        category=OperatorCategory.RAG,
        description="The summary assembler operator.",
        inputs=[
            IOField.build_from(
                "Knowledge", "knowledge", Knowledge, "knowledge datasource"
            )
        ],
        outputs=[
            IOField.build_from(
                "document summary",
                "summary",
                str,
                description="document summary",
            )
        ],
        parameters=[
            Parameter.build_from(
                "LLM Client",
                "llm_client",
                LLMClient,
                optional=True,
                default=None,
                description="The LLM Client.",
            ),
            Parameter.build_from(
                label="model name",
                name="model_name",
                type=str,
                optional=True,
                default="gpt-3.5-turbo",
                description="llm model name",
            ),
            Parameter.build_from(
                label="prompt language",
                name="language",
                type=str,
                optional=True,
                default="en",
                description="prompt language",
            ),
            Parameter.build_from(
                label="max_iteration_with_llm",
                name="max_iteration_with_llm",
                type=int,
                optional=True,
                default=5,
                description="prompt language",
            ),
            Parameter.build_from(
                label="concurrency_limit_with_llm",
                name="concurrency_limit_with_llm",
                type=int,
                optional=True,
                default=3,
                description="The concurrency limit with llm",
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(
        self,
        llm_client: Optional[LLMClient],
        model_name: Optional[str] = "gpt-3.5-turbo",
        language: Optional[str] = "en",
        max_iteration_with_llm: Optional[int] = 5,
        concurrency_limit_with_llm: Optional[int] = 3,
        **kwargs
    ):
        """Create the summary assemble operator.

        Args:
              llm_client: (Optional[LLMClient]) The LLM client.
              model_name: (Optional[str]) The model name.
              language: (Optional[str]) The prompt language.
              max_iteration_with_llm: (Optional[int]) The max iteration with llm.
              concurrency_limit_with_llm: (Optional[int]) The concurrency limit with
                llm.
        """
        super().__init__(**kwargs)
        self._llm_client = llm_client
        self._model_name = model_name
        self._language = language
        self._max_iteration_with_llm = max_iteration_with_llm
        self._concurrency_limit_with_llm = concurrency_limit_with_llm

    async def map(self, knowledge: Knowledge) -> str:
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

    def assemble(self, knowledge: Knowledge) -> Any:
        """Assemble the summary."""
        pass
