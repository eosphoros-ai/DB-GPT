import asyncio

from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.knowledge.factory import KnowledgeFactory
from dbgpt.serve.rag.assembler.embedding import EmbeddingAssembler


async def main():
    pdf_path = "../../../DB-GPT/docs/docs/awel.md"
    knowledge = KnowledgeFactory.from_file_path(pdf_path)
    embedding_model_path = "{your_embedding_model_path}"
    chunk_parameters = ChunkParameters(
        chunk_strategy="CHUNK_BY_SIZE"
    )
    #
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        embedding_model=embedding_model_path,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    chunks = await retriever.aretrieve_with_scores("RAG", 0.3)
    print(f"embedding rag example results:{chunks}")


if __name__ == "__main__":
    asyncio.run(main())
