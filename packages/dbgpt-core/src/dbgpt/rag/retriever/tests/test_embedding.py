from unittest.mock import MagicMock

import pytest

from dbgpt.core import Chunk
from dbgpt.rag.retriever.embedding import EmbeddingRetriever


@pytest.fixture
def top_k():
    return 4


@pytest.fixture
def query():
    return "test query"


@pytest.fixture
def mock_vector_store_connector():
    return MagicMock()


@pytest.fixture
def embedding_retriever(top_k, mock_vector_store_connector):
    return EmbeddingRetriever(
        top_k=top_k,
        query_rewrite=None,
        index_store=mock_vector_store_connector,
    )


def test_retrieve(query, top_k, mock_vector_store_connector, embedding_retriever):
    expected_chunks = [Chunk() for _ in range(top_k)]
    mock_vector_store_connector.similar_search.return_value = expected_chunks

    retrieved_chunks = embedding_retriever._retrieve(query)

    assert len(retrieved_chunks) == top_k
