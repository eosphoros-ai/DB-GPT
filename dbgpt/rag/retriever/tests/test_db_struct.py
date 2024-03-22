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
def dbstruct_retriever(mock_db_connection, mock_vector_store_connector):
    return DBSchemaRetriever(
        connector=mock_db_connection,
        vector_store_connector=mock_vector_store_connector,
    )


def mock_parse_db_summary() -> str:
    """Patch _parse_db_summary method."""
    return "Table summary"


# Mocking the _parse_db_summary method in your test function
@patch.object(
    dbgpt.rag.summary.rdbms_db_summary, "_parse_db_summary", mock_parse_db_summary
)
def test_retrieve_with_mocked_summary(dbstruct_retriever):
    query = "Table summary"
    chunks: List[Chunk] = dbstruct_retriever._retrieve(query)
    assert isinstance(chunks[0], Chunk)
    assert chunks[0].content == "Table summary"


async def async_mock_parse_db_summary() -> str:
    """Asynchronous patch for _parse_db_summary method."""
    return "Table summary"
