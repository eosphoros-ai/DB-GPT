from typing import List
from unittest.mock import MagicMock, patch

import pytest

import dbgpt_ext
from dbgpt.core import Chunk
from dbgpt_ext.rag.retriever.db_schema import DBSchemaRetriever


@pytest.fixture
def mock_db_connection():
    return MagicMock()


@pytest.fixture
def mock_table_vector_store_connector():
    mock_connector = MagicMock()
    mock_connector.vector_store_config.name = "table_name"
    chunk = Chunk(
        content="table_name: user\ncomment: user about dbgpt",
        metadata={
            "field_num": 6,
            "part": "table",
            "separated": 1,
            "table_name": "user",
        },
    )
    mock_connector.similar_search_with_scores = MagicMock(return_value=[chunk])
    return mock_connector


@pytest.fixture
def mock_field_vector_store_connector():
    mock_connector = MagicMock()
    chunk1 = Chunk(
        content="name,age",
        metadata={
            "field_num": 6,
            "part": "field",
            "part_index": 0,
            "separated": 1,
            "table_name": "user",
        },
    )
    chunk2 = Chunk(
        content="address,gender",
        metadata={
            "field_num": 6,
            "part": "field",
            "part_index": 1,
            "separated": 1,
            "table_name": "user",
        },
    )
    chunk3 = Chunk(
        content="mail,phone",
        metadata={
            "field_num": 6,
            "part": "field",
            "part_index": 2,
            "separated": 1,
            "table_name": "user",
        },
    )
    mock_connector.similar_search_with_scores = MagicMock(
        return_value=[chunk1, chunk2, chunk3]
    )
    return mock_connector


@pytest.fixture
def dbstruct_retriever(
    mock_db_connection,
    mock_table_vector_store_connector,
    mock_field_vector_store_connector,
):
    return DBSchemaRetriever(
        connector=mock_db_connection,
        table_vector_store_connector=mock_table_vector_store_connector,
        field_vector_store_connector=mock_field_vector_store_connector,
        separator="--table-field-separator--",
    )


def mock_parse_db_summary() -> str:
    """Patch _parse_db_summary method."""
    return (
        "table_name: user\ncomment: user about dbgpt\n"
        "--table-field-separator--\n"
        "name,age\naddress,gender\nmail,phone"
    )


# Mocking the _parse_db_summary method in your test function
@patch.object(
    dbgpt_ext.rag.summary.rdbms_db_summary, "_parse_db_summary", mock_parse_db_summary
)
def test_retrieve_with_mocked_summary(dbstruct_retriever):
    query = "Table summary"
    chunks: List[Chunk] = dbstruct_retriever._retrieve(query)
    assert isinstance(chunks[0], Chunk)
    assert "-table-field-separator--" in chunks[0].content


def async_mock_parse_db_summary() -> str:
    """Asynchronous patch for _parse_db_summary method."""
    return (
        "table_name: user\ncomment: user about dbgpt\n"
        "--table-field-separator--\n"
        "name,age\naddress,gender\nmail,phone"
    )
