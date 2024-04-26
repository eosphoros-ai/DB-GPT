import asyncio
import os
from typing import Optional

from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH, ROOT_PATH
from dbgpt.core import Embeddings
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.rag.evaluation import RetrieverEvaluator
from dbgpt.rag.evaluation.retriever import (
    RetrieverHitRateMetric,
    RetrieverMRRMetric,
    RetrieverSimilarityMetric,
)
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.rag.operators import EmbeddingRetrieverOperator
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector


def _create_embeddings(
    model_name: Optional[str] = "text2vec-large-chinese",
) -> Embeddings:
    """Create embeddings."""
    return DefaultEmbeddingFactory(
        default_model_name=os.path.join(MODEL_PATH, model_name),
    ).create()


def _create_vector_connector(
    embeddings: Embeddings, space_name: str = "retriever_evaluation_example"
) -> VectorStoreConnector:
    """Create vector connector."""
    return VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name=space_name,
            persist_path=os.path.join(PILOT_PATH, "data"),
        ),
        embedding_fn=embeddings,
    )


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    embeddings = _create_embeddings()
    vector_connector = _create_vector_connector(embeddings)
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_MARKDOWN_HEADER")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        vector_store_connector=vector_connector,
    )
    assembler.persist()

    dataset = [
        {
            "query": "what is awel talk about",
            "contexts": [
                "# What is AWEL? \n\nAgentic Workflow Expression Language(AWEL) is a "
                "set of intelligent agent workflow expression language specially "
                "designed for large model application\ndevelopment. It provides great "
                "functionality and flexibility. Through the AWEL API, you can focus on "
                "the development of business logic for LLMs applications\nwithout "
                "paying attention to cumbersome model and environment details.\n\nAWEL "
                "adopts a layered API design. AWEL's layered API design architecture is "
                "shown in the figure below."
            ],
        },
    ]
    evaluator = RetrieverEvaluator(
        operator_cls=EmbeddingRetrieverOperator,
        embeddings=embeddings,
        operator_kwargs={
            "top_k": 5,
            "vector_store_connector": vector_connector,
        },
    )
    metrics = [
        RetrieverHitRateMetric(),
        RetrieverMRRMetric(),
        RetrieverSimilarityMetric(embeddings=embeddings),
    ]
    results = await evaluator.evaluate(dataset, metrics)
    for result in results:
        for metric in result:
            print("Metric:", metric.metric_name)
            print("Question:", metric.query)
            print("Score:", metric.score)
    print(f"Results:\n{results}")


if __name__ == "__main__":
    asyncio.run(main())
