from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.rag.schemalinker.sql_gen import SqlGen


class SqlGenOperator(MapOperator[Any, Any]):
    """The Sql Generation Operator."""

    def __init__(self, llm: Optional[LLMClient], **kwargs):
        """Init the sql generation operator
        Args:
           llm (Optional[LLMClient]): base llm
        """
        super().__init__(**kwargs)
        self._sql_gen = SqlGen(llm=llm)

    async def map(self, prompt_with_query_and_schema: str) -> str:
        """generate sql by llm.
        Args:
            prompt_with_query_and_schema (str): prompt
        Return:
            str: sql
        """
        return await self._sql_gen.sql_gen(
            prompt_with_query_and_schema=prompt_with_query_and_schema
        )
