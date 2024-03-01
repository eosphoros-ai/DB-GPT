import os
from typing import Dict, List

from pydantic import BaseModel, Field

from dbgpt._private.config import Config
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG, MODEL_PATH, PILOT_PATH
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory
from dbgpt.rag.knowledge.base import KnowledgeType
from dbgpt.rag.operators.knowledge import KnowledgeOperator
from dbgpt.serve.rag.operators.embedding import EmbeddingAssemblerOperator
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

"""AWEL: Simple rag embedding operator example
    
    Examples:
    pre-requirements:
        python examples/awel/simple_rag_embedding_example.py 
        ..code-block:: shell
            curl --location --request POST 'http://127.0.0.1:5555/api/v1/awel/trigger/examples/rag/embedding' \
            --header 'Content-Type: application/json' \
            --data-raw '{
              "url": "https://docs.dbgpt.site/docs/awel"
            }'
"""

CFG = Config()


def _create_vector_connector() -> VectorStoreConnector:
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


class TriggerReqBody(BaseModel):
    url: str = Field(..., description="url")


class RequestHandleOperator(MapOperator[TriggerReqBody, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict:
        params = {
            "url": input_value.url,
        }
        print(f"Receive input value: {input_value}")
        return params


class ResultOperator(MapOperator):
    """The Result Operator."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, chunks: List) -> str:
        result = f"embedding success, there are {len(chunks)} chunks."
        print(result)
        return result


with DAG("simple_sdk_rag_embedding_example") as dag:
    trigger = HttpTrigger(
        "/examples/rag/embedding", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    knowledge_operator = KnowledgeOperator(knowledge_type=KnowledgeType.URL.name)
    vector_connector = _create_vector_connector()
    url_parser_operator = MapOperator(map_function=lambda x: x["url"])
    embedding_operator = EmbeddingAssemblerOperator(
        vector_store_connector=vector_connector,
    )
    output_task = ResultOperator()
    (
        trigger
        >> request_handle_task
        >> url_parser_operator
        >> knowledge_operator
        >> embedding_operator
        >> output_task
    )

if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass
