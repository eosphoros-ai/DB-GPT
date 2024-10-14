import pytest

from dbgpt.datasource.conn_tugraph import TuGraphConnector

# Set database connection parameters.
HOST = "localhost"
PORT = 7687
USER = "admin"
PWD = "73@TuGraph"
DB_NAME = "default"


@pytest.fixture(scope="session")
def connector():
    """Create a TuGraphConnector for the entire test session."""
    # Initialize connection.
    connector = TuGraphConnector.from_uri_db(HOST, PORT, USER, PWD, DB_NAME)
    yield connector
    # Close the connection after all tests are completed.
    connector.close()


def test_get_table_names(connector):
    """Test retrieving table names from the graph database."""
    vertex_tables, edge_tables = connector.get_table_names()
    # Verify the quantity of vertex and edge tables.
    assert len(vertex_tables) == 5
    assert len(edge_tables) == 8


def test_get_columns(connector):
    """Test retrieving columns for a specific table."""
    # Get column information of the vertex table named 'person'.
    columns = connector.get_columns("person", "vertex")
    assert len(columns) == 4
    assert any(col["name"] == "id" for col in columns)


def test_get_indexes(connector):
    """Test retrieving indexes for a specific table."""
    # Get the index information of the vertex table named 'person'.
    indexes = connector.get_indexes("person", "vertex")
    assert len(indexes) > 0


def test_run_without_stream(connector):
    query = "MATCH (n) RETURN n limit 10"
    result = connector.run(query)
    assert len(result) == 10


def test_run_with_stream(connector):
    query = "MATCH (n) RETURN n limit 10"
    result = list(connector.run_stream(query))
    assert len(result) == 10
