import asyncio
import os
from typing import Dict, List

from pydantic import BaseModel, Field

from dbgpt._private.config import Config
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG, MODEL_PATH, PILOT_PATH
from dbgpt.core.awel import DAG, HttpTrigger, JoinOperator, MapOperator
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory
from dbgpt.rag.operators.embedding import EmbeddingRetrieverOperator
from dbgpt.rag.operators.rerank import RerankOperator
from dbgpt.rag.operators.rewrite import QueryRewriteOperator
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

"""AWEL: Simple rag embedding operator example

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
        3. make sure you have vector store.
        if there are no data in vector store, please run examples/awel/simple_rag_embedding_example.py
          
        
    ensure your embedding model in DB-GPT/models/.

    Examples:
        ..code-block:: shell
            DBGPT_SERVER="http://127.0.0.1:5555"
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/rag/retrieve \
            -H "Content-Type: application/json" -d '{ \
                "query": "what is awel talk about?"
            }'
"""

CFG = Config()


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


def _context_join_fn(context_dict: Dict, chunks: List[Chunk]) -> Dict:
    """context Join function for JoinOperator.

    Args:
        context_dict (Dict): context dict
        chunks (List[Chunk]): chunks
    Returns:
        Dict: context dict
    """
    context_dict["context"] = "\n".join([chunk.content for chunk in chunks])
    return context_dict


def _create_vector_connector():
    """Create vector connector."""
    model_name = os.getenv("EMBEDDING_MODEL", "text2vec")
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


with DAG("simple_sdk_rag_retriever_example") as dag:
    vector_connector = _create_vector_connector()
    trigger = HttpTrigger(
        "/examples/rag/retrieve", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    query_parser = MapOperator(map_function=lambda x: x["query"])
    context_join_operator = JoinOperator(combine_function=_context_join_fn)
    rewrite_operator = QueryRewriteOperator(llm_client=OpenAILLMClient())
    retriever_context_operator = EmbeddingRetrieverOperator(
        top_k=3,
        vector_store_connector=vector_connector,
    )
    retriever_operator = EmbeddingRetrieverOperator(
        top_k=3,
        vector_store_connector=vector_connector,
    )
    rerank_operator = RerankOperator()
    model_parse_task = MapOperator(lambda out: out.to_dict())

    trigger >> request_handle_task >> context_join_operator
    (
        trigger
        >> request_handle_task
        >> query_parser
        >> retriever_context_operator
        >> context_join_operator
    )
    context_join_operator >> rewrite_operator >> retriever_operator >> rerank_operator

if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass
