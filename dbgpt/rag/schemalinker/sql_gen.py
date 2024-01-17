from typing import Optional

from dbgpt.core import LLMClient, ModelMessage, ModelMessageRoleType, ModelRequest
from dbgpt.util.chat_util import run_async_tasks


class SqlGen:
    """Sql generation"""

    def __init__(self, llm: Optional[LLMClient] = None, **kwargs):
        """
        Args:
            llm (Optional[LLMClient]): base LLM
        """
        super().__init__(**kwargs)
        self._llm = llm

    async def sql_gen(self, prompt_with_query_and_schema: str) -> str:
        """sql generation by llm.
        Args:
            prompt_with_query_and_schema (str): prompt text
        Return:
            str: sql
        """
        messages = [
            ModelMessage(
                role=ModelMessageRoleType.SYSTEM, content=prompt_with_query_and_schema
            )
        ]
        request = ModelRequest(model="gpt-3.5-turbo", messages=messages)
        tasks = [self._llm.generate(request)]
        output = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        sql = output[0].text
        return sql
