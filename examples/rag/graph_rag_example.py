import asyncio
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.storage.knowledge_graph.knowledge_graph import BuiltinKnowledgeGraphConfig
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

"""GraphRAG example.
    pre-requirements:
    * Set LLM config (url/sk) in `.env`.
    * Setup/startup TuGraph from: https://github.com/TuGraph-family/tugraph-db
    * Config TuGraph following the format below. 
    ```
    GRAPH_STORE_TYPE=TuGraph
    TUGRAPH_HOST=127.0.0.1
    TUGRAPH_PORT=7687
    TUGRAPH_USERNAME=admin
    TUGRAPH_PASSWORD=73@TuGraph
    ```

    Examples:
        ..code-block:: shell
            python examples/rag/graph_rag_example.py
"""


def _create_kg_connector():
    """Create knowledge graph connector."""
    return VectorStoreConnector(
        vector_store_type="KnowledgeGraph",
        vector_store_config=VectorStoreConfig(
            name="graph_rag_test",
            embedding_fn=None,
            llm_client=OpenAILLMClient(),
            model_name="gpt-3.5-turbo",
        ),
    )


async def main():
    file_path = os.path.join(ROOT_PATH, "examples/test_files/tranformers_story.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    vector_connector = _create_kg_connector()
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
    chunks = await retriever.aretrieve_with_scores(
        "What actions has Megatron taken ?", score_threshold=0.3
    )
    print(f"embedding rag example results:{chunks}")
    vector_connector.delete_vector_name("graph_rag_test")


if __name__ == "__main__":
    asyncio.run(main())
