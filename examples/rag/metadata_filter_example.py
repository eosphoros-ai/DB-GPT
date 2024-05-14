"""Rag Metadata Properties filter example.
    pre-requirements:
    make sure you have set your embedding model path in your example code.

    Examples:
        ..code-block:: shell
            python examples/rag/metadata_filter_example.py
"""
import asyncio
import os

from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH, ROOT_PATH
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.storage.vector_store.filters import MetadataFilter, MetadataFilters


def _create_vector_connector():
    """Create vector connector."""
    return VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name="example_metadata_filter_name",
            persist_path=os.path.join(PILOT_PATH, "data"),
        ),
        embedding_fn=DefaultEmbeddingFactory(
            default_model_name=os.path.join(MODEL_PATH, "text2vec-large-chinese"),
        ).create(),
    )


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    vector_connector = _create_vector_connector()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_MARKDOWN_HEADER")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        vector_store_connector=vector_connector,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    # create metadata filter
    metadata_filter = MetadataFilter(key="Header2", value="AWEL Design")
    filters = MetadataFilters(filters=[metadata_filter])
    chunks = await retriever.aretrieve_with_scores(
        "what is awel talk about", 0.0, filters
    )
    print(f"embedding rag example results:{chunks}")


if __name__ == "__main__":
    asyncio.run(main())
