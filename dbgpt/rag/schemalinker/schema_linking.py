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
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.rag.schemalinker.base_linker import BaseSchemaLinker
from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.chat_util import run_async_tasks

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
        connection: RDBMSConnector,
        model_name: str,
        llm: LLMClient,
        top_k: int = 5,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs
    ):
        """Create the schema linking instance.

        Args:
           connection (Optional[RDBMSConnector]): RDBMSConnector connection.
           llm (Optional[LLMClient]): base llm
        """
        super().__init__(**kwargs)
        self._top_k = top_k
        self._connection = connection
        self._llm = llm
        self._model_name = model_name
        self._vector_store_connector = vector_store_connector

    def _schema_linking(self, query: str) -> List:
        """Get all db schema info."""
        table_summaries = _parse_db_summary(self._connection)
        chunks = [Chunk(content=table_summary) for table_summary in table_summaries]
        chunks_content = [chunk.content for chunk in chunks]
        return chunks_content

    def _schema_linking_with_vector_db(self, query: str) -> List[Chunk]:
        queries = [query]
        if not self._vector_store_connector:
            raise ValueError("Vector store connector is not provided.")
        candidates = [
            self._vector_store_connector.similar_search(query, self._top_k)
            for query in queries
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
