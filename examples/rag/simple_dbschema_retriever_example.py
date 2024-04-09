"""AWEL: Simple rag db schema embedding operator example

    if you not set vector_store_connector, it will return all tables schema in database.
    ```
    retriever_task = DBSchemaRetrieverOperator(
        connector=_create_temporary_connection()
    )
    ```
    if you set vector_store_connector, it will recall topk similarity tables schema in database.
    ```
    retriever_task = DBSchemaRetrieverOperator(
        connector=_create_temporary_connection()
        top_k=1,
        vector_store_connector=vector_store_connector
    )
    ```

    Examples:
        ..code-block:: shell
            curl --location 'http://127.0.0.1:5555/api/v1/awel/trigger/examples/rag/dbschema' \
            --header 'Content-Type: application/json' \
            --data '{"query": "what is user name?"}'
"""

import os
from typing import Dict, List

from dbgpt._private.config import Config
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG, PILOT_PATH
from dbgpt.core import Chunk
from dbgpt.core.awel import DAG, HttpTrigger, InputOperator, JoinOperator, MapOperator
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.rag.operators import DBSchemaAssemblerOperator, DBSchemaRetrieverOperator
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

CFG = Config()


def _create_vector_connector():
    """Create vector connector."""
    return VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name="vector_name",
            persist_path=os.path.join(PILOT_PATH, "data"),
        ),
        embedding_fn=DefaultEmbeddingFactory(
            default_model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
        ).create(),
    )


def _create_temporary_connection():
    """Create a temporary database connection for testing."""
    connect = SQLiteTempConnector.create_temporary_db()
    connect.create_temp_tables(
        {
            "user": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "Tom", 10),
                    (2, "Jerry", 16),
                    (3, "Jack", 18),
                    (4, "Alice", 20),
                    (5, "Bob", 22),
                ],
            }
        }
    )
    return connect


def _join_fn(chunks: List[Chunk], query: str) -> str:
    print(f"db schema info is {[chunk.content for chunk in chunks]}")
    return query


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


with DAG("simple_rag_db_schema_example") as dag:
    trigger = HttpTrigger(
        "/examples/rag/dbschema", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    query_operator = MapOperator(lambda request: request["query"])
    vector_store_connector = _create_vector_connector()
    connector = _create_temporary_connection()
    assembler_task = DBSchemaAssemblerOperator(
        connector=connector,
        vector_store_connector=vector_store_connector,
    )
    join_operator = JoinOperator(combine_function=_join_fn)
    retriever_task = DBSchemaRetrieverOperator(
        connector=_create_temporary_connection(),
        top_k=1,
        vector_store_connector=vector_store_connector,
    )
    result_parse_task = MapOperator(lambda chunks: [chunk.content for chunk in chunks])
    trigger >> assembler_task >> join_operator
    trigger >> request_handle_task >> query_operator >> join_operator
    join_operator >> retriever_task >> result_parse_task


if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass
