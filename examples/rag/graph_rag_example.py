import os

import pytest

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.core import Chunk, HumanPromptTemplate, ModelMessage, ModelRequest
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.rag.retriever import RetrieverStrategy
from dbgpt.storage.knowledge_graph.community_summary import (
    CommunitySummaryKnowledgeGraph,
    CommunitySummaryKnowledgeGraphConfig,
)
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)

"""GraphRAG example.
    ```
    # Set LLM config (url/sk) in `.env`.
    # Install pytest utils: `pip install pytest pytest-asyncio`
    GRAPH_STORE_TYPE=TuGraph
    TUGRAPH_HOST=127.0.0.1
    TUGRAPH_PORT=7687
    TUGRAPH_USERNAME=admin
    TUGRAPH_PASSWORD=73@TuGraph
    ```
    Examples:
        ..code-block:: shell
            pytest -s examples/rag/graph_rag_example.py
"""

llm_client = OpenAILLMClient()
model_name = "gpt-4o-mini"


@pytest.mark.asyncio
async def test_naive_graph_rag():
    await __run_graph_rag(
        knowledge_file="examples/test_files/graphrag-mini.md",
        chunk_strategy="CHUNK_BY_SIZE",
        knowledge_graph=__create_naive_kg_connector(),
        question="What's the relationship between TuGraph and DB-GPT ?",
    )


@pytest.mark.asyncio
async def test_community_graph_rag():
    await __run_graph_rag(
        knowledge_file="examples/test_files/graphrag-mini.md",
        chunk_strategy="CHUNK_BY_MARKDOWN_HEADER",
        knowledge_graph=__create_community_kg_connector(),
        question="What's the relationship between TuGraph and DB-GPT ?",
    )


def __create_naive_kg_connector():
    """Create knowledge graph connector."""
    return BuiltinKnowledgeGraph(
        config=BuiltinKnowledgeGraphConfig(
            name="naive_graph_rag_test",
            embedding_fn=None,
            llm_client=llm_client,
            model_name=model_name,
            graph_store_type="MemoryGraph",
        ),
    )


def __create_community_kg_connector():
    """Create community knowledge graph connector."""
    return CommunitySummaryKnowledgeGraph(
        config=CommunitySummaryKnowledgeGraphConfig(
            name="community_graph_rag_test",
            embedding_fn=DefaultEmbeddingFactory.openai(),
            llm_client=llm_client,
            model_name=model_name,
            graph_store_type="TuGraphGraph",
        ),
    )


async def ask_chunk(chunk: Chunk, question) -> str:
    rag_template = (
        "Based on the following [Context] {context}, " "answer [Question] {question}."
    )
    template = HumanPromptTemplate.from_template(rag_template)
    messages = template.format_messages(context=chunk.content, question=question)
    model_messages = ModelMessage.from_base_messages(messages)
    request = ModelRequest(model=model_name, messages=model_messages)
    response = await llm_client.generate(request=request)

    if not response.success:
        code = str(response.error_code)
        reason = response.text
        raise Exception(f"request llm failed ({code}) {reason}")

    return response.text


async def __run_graph_rag(knowledge_file, chunk_strategy, knowledge_graph, question):
    file_path = os.path.join(ROOT_PATH, knowledge_file).format()
    knowledge = KnowledgeFactory.from_file_path(file_path)
    try:
        chunk_parameters = ChunkParameters(chunk_strategy=chunk_strategy)

        # get embedding assembler
        assembler = await EmbeddingAssembler.aload_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            index_store=knowledge_graph,
            retrieve_strategy=RetrieverStrategy.GRAPH,
        )
        await assembler.apersist()

        # get embeddings retriever
        retriever = assembler.as_retriever(1)
        chunks = await retriever.aretrieve_with_scores(question, score_threshold=0.3)

        # chat
        print(f"{await ask_chunk(chunks[0], question)}")

    finally:
        knowledge_graph.delete_vector_name(knowledge_graph.get_config().name)
