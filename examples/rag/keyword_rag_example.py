import asyncio
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.storage.full_text.elasticsearch import (
    ElasticDocumentConfig,
    ElasticDocumentStore,
)

"""Keyword rag example.
    pre-requirements:
    set your Elasticsearch environment.

    Examples:
        ..code-block:: shell
            python examples/rag/keyword_rag_example.py
"""


def _create_es_connector():
    """Create es connector."""
    config = ElasticDocumentConfig(
        name="keyword_rag_test",
        uri="localhost",
        port="9200",
        user="elastic",
        password="dbgpt",
    )

    return ElasticDocumentStore(config)


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    keyword_store = _create_es_connector()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        index_store=keyword_store,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    chunks = await retriever.aretrieve_with_scores("what is awel talk about", 0.3)
    print(f"keyword rag example results:{chunks}")


if __name__ == "__main__":
    asyncio.run(main())
