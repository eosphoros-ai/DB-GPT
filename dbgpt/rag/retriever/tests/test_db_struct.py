from typing import List
from unittest.mock import MagicMock, patch

import pytest

import dbgpt
from dbgpt.core import Chunk
from dbgpt.rag.retriever.db_schema import DBSchemaRetriever
from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary


@pytest.fixture
def mock_db_connection():
    return MagicMock()


@pytest.fixture
def mock_vector_store_connector():
    mock_connector = MagicMock()
    mock_connector.similar_search.return_value = [Chunk(content="Table summary")] * 4
    return mock_connector


@pytest.fixture
def db_struct_retriever(mock_db_connection, mock_vector_store_connector):
    return DBSchemaRetriever(
        connector=mock_db_connection,
        index_store=mock_vector_store_connector,
    )


def mock_parse_db_summary(conn) -> List[str]:
    """Patch _parse_db_summary method."""
    return ["Table summary"]


# Mocking the _parse_db_summary method in your test function
@patch.object(
    dbgpt.rag.summary.rdbms_db_summary, "_parse_db_summary", mock_parse_db_summary
)
def test_retrieve_with_mocked_summary(db_struct_retriever):
    query = "Table summary"
    chunks: List[Chunk] = db_struct_retriever._retrieve(query)
    assert isinstance(chunks[0], Chunk)
    assert chunks[0].content == "Table summary"


@pytest.mark.asyncio
@patch.object(
    dbgpt.rag.summary.rdbms_db_summary, "_parse_db_summary", mock_parse_db_summary
)
async def test_aretrieve_with_mocked_summary(db_struct_retriever):
    query = "Table summary"
    chunks: List[Chunk] = await db_struct_retriever._aretrieve(query)
    assert isinstance(chunks[0], Chunk)
    assert chunks[0].content == "Table summary"
