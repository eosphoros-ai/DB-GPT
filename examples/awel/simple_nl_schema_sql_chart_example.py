import os
from typing import Dict

from pydantic import BaseModel, Field

from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH
from dbgpt.core.awel import DAG, HttpTrigger, JoinOperator, MapOperator
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnect
from dbgpt.model import OpenAILLMClient
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory
from dbgpt.rag.operator.chart_draw import ChartDrawOperator
from dbgpt.rag.operator.schema_linking import SchemaLinkingOperator
from dbgpt.rag.operator.sql_gen import SqlGenOperator
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

"""AWEL: Simple nl-schemalinking-sql-chart operator example

    pre-requirements:
        1. install openai python sdk
        ```
            pip install openai
        ```
        2. set openai key and base
        ```
            export OPENAI_API_KEY={your_openai_key}
            export OPENAI_API_BASE={your_openai_base}
        ```
        or
        ```
            import os
            os.environ["OPENAI_API_KEY"] = {your_openai_key}
            os.environ["OPENAI_API_BASE"] = {your_openai_base}
        ```
        python examples/awel/simple_nl_schema_sql_chart_example.py
    Examples:
        ..code-block:: shell
        curl --location 'http://127.0.0.1:5555/api/v1/awel/trigger/examples/rag/schema_linking' \
--header 'Content-Type: application/json' \
--data '{"query": "Statistics of user age in the user table are based on three categories: age is less than 10, age is greater than or equal to 10 and less than or equal to 20, and age is greater than 20. The first column of the statistical results is different ages, and the second column is count."}' 
"""

INSTRUCTION = (
    "I want you to act as a SQL terminal in front of an example database, you need only to return the sql "
    "command to me.Below is an instruction that describes a task, Write a response that appropriately "
    "completes the request.\n###Instruction:\n{}"
)
INPUT_PROMPT = "\n###Input:\n{}\n###Response:"


def _create_vector_connector():
    """Create vector connector."""
    return VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name="vector_name",
            persist_path=os.path.join(PILOT_PATH, "data"),
        ),
        embedding_fn=DefaultEmbeddingFactory(
            default_model_name=os.path.join(MODEL_PATH, "text2vec-large-chinese"),
        ).create(),
    )


def _create_temporary_connection():
    """Create a temporary database connection for testing."""
    connect = SQLiteTempConnect.create_temporary_db()
    connect.create_temp_tables(
        {
            "user": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "Tom", 8),
                    (2, "Jerry", 16),
                    (3, "Jack", 18),
                    (4, "Alice", 20),
                    (5, "Bob", 22),
                ],
            }
        }
    )
    connect.create_temp_tables(
        {
            "job": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "student", 8),
                    (2, "student", 16),
                    (3, "student", 18),
                    (4, "teacher", 20),
                    (5, "teacher", 22),
                ],
            }
        }
    )
    connect.create_temp_tables(
        {
            "student": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                    "info": "TEXT",
                },
                "data": [
                    (1, "Andy", 8, "good"),
                    (2, "Jerry", 16, "bad"),
                    (3, "Wendy", 18, "good"),
                    (4, "Spider", 20, "bad"),
                    (5, "David", 22, "bad"),
                ],
            }
        }
    )
    return connect


def _prompt_join_fn(query: str, chunks: str) -> str:
    prompt = INSTRUCTION.format(chunks + INPUT_PROMPT.format(query))
    return prompt


class TriggerReqBody(BaseModel):
    query: str = Field(..., description="User query")


class RequestHandleOperator(MapOperator[TriggerReqBody, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict:
        params = {
            "query": input_value.query,
        }
        print(f"Receive input value: {input_value}")
        return params


with (DAG("simple_nl_schema_sql_chart_example") as dag):
    trigger = HttpTrigger(
        "/examples/rag/schema_linking", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    query_operator = MapOperator(lambda request: request["query"])
    llm = OpenAILLMClient()
    retriever_task = SchemaLinkingOperator(
        connection=_create_temporary_connection(), llm=llm
    )
    # query + schema --> prompt
    prompt_operator = JoinOperator(combine_function=_prompt_join_fn)
    sql_gen_operator = SqlGenOperator(llm=llm)
    # # sql --> result in db
    # sql_exec_operator= SqlExecOperator(connection=_create_temporary_connection())
    draw_chart_operator = ChartDrawOperator(connection=_create_temporary_connection())
    # join (query, schema)
    trigger >> request_handle_task >> query_operator >> prompt_operator
    (
        trigger
        >> request_handle_task
        >> query_operator
        >> retriever_task
        >> prompt_operator
    )
    prompt_operator >> sql_gen_operator >> draw_chart_operator

if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass
