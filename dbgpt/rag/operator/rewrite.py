from typing import Any, List, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.task.base import IN
from dbgpt.rag.retriever.rewrite import QueryRewrite


class QueryRewriteOperator(MapOperator[Any, Any]):
    """The Rewrite Operator."""

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
