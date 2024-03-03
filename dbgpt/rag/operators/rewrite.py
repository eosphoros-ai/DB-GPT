from typing import Any, List, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.core.awel.task.base import IN
from dbgpt.rag.retriever.rewrite import QueryRewrite


class QueryRewriteOperator(MapOperator[Any, Any]):
    """The Rewrite Operator."""

    metadata = ViewMetadata(
        label="Query Rewrite Operator",
        name="query_rewrite_operator",
        category=OperatorCategory.RAG,
        description="query rewrite operator.",
        inputs=[
            IOField.build_from("query_context", "query_context", dict, "query context")
        ],
        outputs=[
            IOField.build_from(
                "rewritten queries",
                "queries",
                List[str],
                description="rewritten queries",
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
                label="nums",
                name="nums",
                type=int,
                optional=True,
                default=5,
                description="rewrite query nums",
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(
        self,
        llm_client: Optional[LLMClient],
        model_name: Optional[str] = None,
        language: Optional[str] = "en",
        nums: Optional[int] = 1,
        **kwargs
    ):
        """Init the query rewrite operator.
        Args:
            llm_client (Optional[LLMClient]): The LLM client.
            model_name (Optional[str]): The model name.
            language (Optional[str]): The prompt language.
            nums (Optional[int]): The number of the rewrite results.
        """
        super().__init__(**kwargs)
        self._nums = nums
        self._rewrite = QueryRewrite(
            llm_client=llm_client,
            model_name=model_name,
            language=language,
        )

    async def map(self, query_context: IN) -> List[str]:
        """Rewrite the query."""
        query = query_context.get("query")
        context = query_context.get("context")
        return await self._rewrite.rewrite(
            origin_query=query, context=context, nums=self._nums
        )
