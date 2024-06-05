import asyncio
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler.bm25 import BM25Assembler
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.storage.vector_store.elastic_store import ElasticsearchVectorConfig

"""Embedding rag example.
    pre-requirements:
    set your elasticsearch config in your example code.

    Examples:
        ..code-block:: shell
            python examples/rag/bm25_retriever_example.py
"""


def _create_es_config():
    """Create vector connector."""
    return ElasticsearchVectorConfig(
        name="bm25_es_dbgpt",
        uri="localhost",
        port="9200",
        user="elastic",
        password="dbgpt",
    )


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    es_config = _create_es_config()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    # create bm25 assembler
    assembler = BM25Assembler.load_from_knowledge(
        knowledge=knowledge,
        es_config=es_config,
        chunk_parameters=chunk_parameters,
    )
    assembler.persist()
    # get bm25 retriever
    retriever = assembler.as_retriever(3)
    chunks = retriever.retrieve_with_scores("what is awel talk about", 0.3)
    print(f"bm25 rag example results:{chunks}")


if __name__ == "__main__":
    asyncio.run(main())
