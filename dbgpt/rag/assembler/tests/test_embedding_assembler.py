from unittest.mock import MagicMock

import pytest

from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
from dbgpt.rag.assembler.db_schema import DBSchemaAssembler
from dbgpt.rag.chunk_manager import ChunkParameters, SplitterType
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddings, EmbeddingFactory
from dbgpt.rag.text_splitter.text_splitter import RDBTextSplitter
from dbgpt.serve.rag.connector import VectorStoreConnector


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
                    "address": "TEXT",
                    "phone": "TEXT",
                    "email": "TEXT",
                    "gender": "TEXT",
                    "birthdate": "TEXT",
                    "occupation": "TEXT",
                    "education": "TEXT",
                    "marital_status": "TEXT",
                    "nationality": "TEXT",
                    "height": "REAL",
                    "weight": "REAL",
                    "blood_type": "TEXT",
                    "emergency_contact": "TEXT",
                    "created_at": "TEXT",
                    "updated_at": "TEXT",
                }
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
def mock_table_vector_store_connector():
    mock_connector = MagicMock(spec=VectorStoreConnector)
    mock_connector.vector_store_config.name = "table_vector_store_name"
    mock_connector.current_embeddings = DefaultEmbeddings()
    return mock_connector


def test_load_knowledge(
    mock_db_connection,
    mock_chunk_parameters,
    mock_embedding_factory,
    mock_table_vector_store_connector,
):
    mock_chunk_parameters.chunk_strategy = "CHUNK_BY_SIZE"
    mock_chunk_parameters.text_splitter = RDBTextSplitter(
        separator="--table-field-separator--"
    )
    mock_chunk_parameters.splitter_type = SplitterType.USER_DEFINE
    assembler = DBSchemaAssembler(
        connector=mock_db_connection,
        chunk_parameters=mock_chunk_parameters,
        embeddings=mock_embedding_factory.create(),
        table_vector_store_connector=mock_table_vector_store_connector,
        max_seq_length=10,
    )
    assert len(assembler._chunks) > 1
