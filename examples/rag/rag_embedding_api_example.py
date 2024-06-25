"""A RAG example using the OpenAPIEmbeddings.

Example:

    Test with `OpenAI embeddings
    <https://platform.openai.com/docs/api-reference/embeddings/create>`_.

    .. code-block:: shell

        export API_SERVER_BASE_URL=${OPENAI_API_BASE:-"https://api.openai.com/v1"}
        export API_SERVER_API_KEY="${OPENAI_API_KEY}"
        export API_SERVER_EMBEDDINGS_MODEL="text-embedding-ada-002"
        python examples/rag/rag_embedding_api_example.py

    Test with DB-GPT `API Server
    <https://docs.dbgpt.site/docs/installation/advanced_usage/OpenAI_SDK_call#start-apiserver>`_.

    .. code-block:: shell
        export API_SERVER_BASE_URL="http://localhost:8100/api/v1"
        export API_SERVER_API_KEY="your_api_key"
        export API_SERVER_EMBEDDINGS_MODEL="text2vec"
        python examples/rag/rag_embedding_api_example.py

"""
import asyncio
import os
from typing import Optional

from dbgpt.configs.model_config import PILOT_PATH, ROOT_PATH
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.embedding import OpenAPIEmbeddings
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.storage.vector_store.chroma_store import ChromaStore, ChromaVectorConfig


def _create_embeddings(
    api_url: str = None, api_key: Optional[str] = None, model_name: Optional[str] = None
) -> OpenAPIEmbeddings:
    if not api_url:
        api_server_base_url = os.getenv(
            "API_SERVER_BASE_URL", "http://localhost:8100/api/v1/"
        )
        api_url = f"{api_server_base_url}/embeddings"
    if not api_key:
        api_key = os.getenv("API_SERVER_API_KEY")

    if not model_name:
        model_name = os.getenv("API_SERVER_EMBEDDINGS_MODEL", "text2vec")

    return OpenAPIEmbeddings(api_url=api_url, api_key=api_key, model_name=model_name)


def _create_vector_connector():
    """Create vector connector."""
    config = ChromaVectorConfig(
        persist_path=PILOT_PATH,
        name="embedding_api_rag_test",
        embedding_fn=_create_embeddings(),
    )

    return ChromaStore(config)


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    vector_store = _create_vector_connector()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        index_store=vector_store,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    chunks = await retriever.aretrieve_with_scores("what is awel talk about", 0.3)
    print(f"embedding rag example results:{chunks}")
    vector_store.delete_vector_name("embedding_api_rag_test")


if __name__ == "__main__":
    asyncio.run(main())
