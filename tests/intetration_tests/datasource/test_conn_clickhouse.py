import pytest

from dbgpt.datasource.rdbms.conn_clickhouse import ClickhouseConnect


@pytest.fixture
def db():
    conn = ClickhouseConnect.from_uri_db("localhost", 8123, "default", "", "default")
    yield conn
