import os

import pytest

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.core import ModelMessage, HumanPromptTemplate, ModelRequest, Chunk
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.knowledge import KnowledgeFactory
from dbgpt.rag.retriever import RetrieverStrategy
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)

"""GraphRAG example.
    pre-requirements:
    * Set LLM config (url/sk) in `.env`.
    * Install pytest utils: `pip install pytest pytest-asyncio`
    Examples:
        ..code-block:: shell
            pytest -s examples/rag/graph_rag_example.py
"""

llm_client = OpenAILLMClient()
model_name = "gpt-4o-mini"
rag_template = (
    "Based on the following [Context] {context}, answer [Question] {question}."
)

file = "examples/test_files/graphrag-mini.md"
question = "What is TuGraph ?"


def _create_kg_connector():
    """Create knowledge graph connector."""
    return BuiltinKnowledgeGraph(
        config=BuiltinKnowledgeGraphConfig(
            name="graph_rag_test",
            embedding_fn=None,
            llm_client=llm_client,
            model_name=model_name,
            graph_store_type='MemoryGraph'
        ),
    )


async def chat_rag(chunk: Chunk) -> str:
    template = HumanPromptTemplate.from_template(rag_template)
    messages = template.format_messages(
        context=chunk,
        question=question
    )
    model_messages = ModelMessage.from_base_messages(messages)
    request = ModelRequest(model=model_name, messages=model_messages)
    response = await llm_client.generate(request=request)

    if not response.success:
        code = str(response.error_code)
        reason = response.text
        raise Exception(f"request llm failed ({code}) {reason}")

    return response.text


@pytest.mark.asyncio
async def test_naive_graph_rag():
    file_path = os.path.join(ROOT_PATH, file)
    knowledge = KnowledgeFactory.from_file_path(file_path)
    graph_store = _create_kg_connector()

    try:
        chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")

        # get embedding assembler
        assembler = await EmbeddingAssembler.aload_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            index_store=graph_store,
            retrieve_strategy=RetrieverStrategy.GRAPH,
        )
        await assembler.apersist()

        # get embeddings retriever
        retriever = assembler.as_retriever(1)
        chunks = await retriever.aretrieve_with_scores(
            question, score_threshold=0.3
        )

        # chat
        print(f"{await chat_rag(chunks[0])}")

    except Exception as e:
        graph_store.delete_vector_name("graph_rag_test")
        raise e


@pytest.mark.asyncio
async def test_community_graph_rag():
    pass
