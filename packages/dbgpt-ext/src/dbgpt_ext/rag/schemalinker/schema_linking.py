"""SchemaLinking by LLM."""

from functools import reduce
from typing import List, Optional, cast

from dbgpt.core import (
    Chunk,
    LLMClient,
    ModelMessage,
    ModelMessageRoleType,
    ModelRequest,
)
from dbgpt.datasource.base import BaseConnector
from dbgpt.storage.base import IndexStoreBase
from dbgpt.util.chat_util import run_async_tasks
from dbgpt_ext.rag.schemalinker.base_linker import BaseSchemaLinker
from dbgpt_ext.rag.summary.rdbms_db_summary import _parse_db_summary

INSTRUCTION = """
You need to filter out the most relevant database table schema information (it may be a
 single table or multiple tables) required to generate the SQL of the question query
 from the given database schema information. First, I will show you an example of an
 instruction followed by the correct schema response. Then, I will give you a new
 instruction, and you should write the schema response that appropriately completes the
 request.

### Example1 Instruction:
['job(id, name, age)', 'user(id, name, age)', 'student(id, name, age, info)']
### Example1 Input:
Find the age of student table
### Example1 Response:
['student(id, name, age, info)']
###New Instruction:
{}
"""

INPUT_PROMPT = "\n###New Input:\n{}\n###New Response:"


class SchemaLinking(BaseSchemaLinker):
    """SchemaLinking by LLM."""

    def __init__(
        self,
        connector: BaseConnector,
        model_name: str,
        llm: LLMClient,
        top_k: int = 5,
        index_store: Optional[IndexStoreBase] = None,
    ):
        """Create the schema linking instance.

        Args:
           connection (Optional[BaseConnector]): BaseConnector connection.
           llm (Optional[LLMClient]): base llm
        """
        self._top_k = top_k
        self._connector = connector
        self._llm = llm
        self._model_name = model_name
        self._index_store = index_store

    def _schema_linking(self, query: str) -> List:
        """Get all db schema info."""
        table_summaries = _parse_db_summary(self._connector)
        chunks = [Chunk(content=table_summary) for table_summary in table_summaries]
        chunks_content = [chunk.content for chunk in chunks]
        return chunks_content

    def _schema_linking_with_vector_db(self, query: str) -> List[Chunk]:
        queries = [query]
        if not self._index_store:
            raise ValueError("Vector store connector is not provided.")
        candidates = [
            self._index_store.similar_search(query, self._top_k) for query in queries
        ]
        return cast(List[Chunk], reduce(lambda x, y: x + y, candidates))

    async def _schema_linking_with_llm(self, query: str) -> List:
        chunks_content = self.schema_linking(query)
        schema_prompt = INSTRUCTION.format(
            str(chunks_content) + INPUT_PROMPT.format(query)
        )
        messages = [
            ModelMessage(role=ModelMessageRoleType.SYSTEM, content=schema_prompt)
        ]
        request = ModelRequest(model=self._model_name, messages=messages)
        tasks = [self._llm.generate(request)]
        # get accurate schem info by llm
        schema = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        schema_text = schema[0].text
        return schema_text
