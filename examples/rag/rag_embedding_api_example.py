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
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.embedding import OpenAPIEmbeddings
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.serve.rag.assembler.embedding import EmbeddingAssembler
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector


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

    return VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name="example_embedding_api_vector_store_name",
            persist_path=os.path.join(PILOT_PATH, "data"),
        ),
        embedding_fn=_create_embeddings(),
    )


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    vector_connector = _create_vector_connector()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        vector_store_connector=vector_connector,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    chunks = await retriever.aretrieve_with_scores("what is awel talk about", 0.3)
    print(f"embedding rag example results:{chunks}")


if __name__ == "__main__":
    asyncio.run(main())
