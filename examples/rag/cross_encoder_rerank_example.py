"""This example demonstrates how to use the cross-encoder reranker
to rerank the retrieved chunks.
The cross-encoder reranker is a neural network model that takes a query
and a chunk as input and outputs a score that represents the relevance of the chunk
to the query.

Download pretrained cross-encoder models can be found at https://huggingface.co/models.
Example:
    python examples/rag/cross_encoder_rerank_example.py
"""
import asyncio
import os

from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH, ROOT_PATH
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.rag.retriever.rerank import CrossEncoderRanker
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector


def _create_vector_connector():
    """Create vector connector."""
    print(f"persist_path:{os.path.join(PILOT_PATH, 'data')}")
    return VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name="example_cross_encoder_rerank",
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
    query = "what is awel talk about"
    chunks = await retriever.aretrieve_with_scores(query, 0.3)

    print("before rerank results:\n")
    for i, chunk in enumerate(chunks):
        print(f"----{i+1}.chunk content:{chunk.content}\n score:{chunk.score}")
    # cross-encoder rerank
    cross_encoder_model = os.path.join(MODEL_PATH, "bge-reranker-base")
    rerank = CrossEncoderRanker(topk=3, model=cross_encoder_model)
    new_chunks = rerank.rank(chunks, query=query)
    print("after cross-encoder rerank results:\n")
    for i, chunk in enumerate(new_chunks):
        print(f"----{i+1}.chunk content:{chunk.content}\n score:{chunk.score}")


if __name__ == "__main__":
    asyncio.run(main())
