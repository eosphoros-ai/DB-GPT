import asyncio
import os
from typing import Dict, List

from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH
from dbgpt.core.awel import DAG, InputOperator, MapOperator, SimpleCallDataInputSource
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory
from dbgpt.rag.operator.knowledge import KnowledgeOperator
from dbgpt.serve.rag.operators.embedding import EmbeddingAssemblerOperator
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

"""AWEL: Simple rag embedding operator example

    pre-requirements:
    set your file path in your example code.
    Examples:
        ..code-block:: shell
            python examples/awel/simple_rag_embedding_example.py
"""


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


class ResultOperator(MapOperator):
    """The Result Operator."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, chunks: List) -> str:
        result = f"embedding success, there are {len(chunks)} chunks."
        print(result)
        return result


with DAG("simple_sdk_rag_embedding_example") as dag:
    knowledge_operator = KnowledgeOperator()
    vector_connector = _create_vector_connector()
    input_task = InputOperator(input_source=SimpleCallDataInputSource())
    file_path_parser = MapOperator(map_function=lambda x: x["file_path"])
    embedding_operator = EmbeddingAssemblerOperator(
        vector_store_connector=vector_connector,
    )
    output_task = ResultOperator()
    (
        input_task
        >> file_path_parser
        >> knowledge_operator
        >> embedding_operator
        >> output_task
    )

if __name__ == "__main__":
    input_data = {
        "data": {
            "file_path": "docs/docs/awel.md",
        }
    }
    output = asyncio.run(output_task.call(call_data=input_data))
