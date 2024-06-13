from unittest.mock import MagicMock

import pytest

from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
from dbgpt.rag.assembler.db_schema import DBSchemaAssembler
from dbgpt.rag.chunk_manager import ChunkParameters, SplitterType
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.text_splitter.text_splitter import CharacterTextSplitter
from dbgpt.storage.vector_store.chroma_store import ChromaStore


@pytest.fixture
def mock_db_connection():
    """Create a temporary database connection for testing."""
    connect = SQLiteTempConnector.create_temporary_db()
    connect.create_temp_tables(
        {
            "user": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "Tom", 10),
                    (2, "Jerry", 16),
                    (3, "Jack", 18),
                    (4, "Alice", 20),
                    (5, "Bob", 22),
                ],
            }
        }
    )
    return connect


@pytest.fixture
def mock_chunk_parameters():
    return MagicMock(spec=ChunkParameters)


@pytest.fixture
def mock_embedding_factory():
    return MagicMock(spec=EmbeddingFactory)


@pytest.fixture
def mock_vector_store_connector():
    return MagicMock(spec=ChromaStore)


def test_load_knowledge(
    mock_db_connection,
    mock_chunk_parameters,
    mock_embedding_factory,
    mock_vector_store_connector,
):
    mock_chunk_parameters.chunk_strategy = "CHUNK_BY_SIZE"
    mock_chunk_parameters.text_splitter = CharacterTextSplitter()
    mock_chunk_parameters.splitter_type = SplitterType.USER_DEFINE
    assembler = DBSchemaAssembler(
        connector=mock_db_connection,
        chunk_parameters=mock_chunk_parameters,
        embeddings=mock_embedding_factory.create(),
        index_store=mock_vector_store_connector,
    )
    assert len(assembler._chunks) == 1
