"""Unit tests for the PostgreSQL connector's schema-scoped introspection."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from dbgpt_ext.datasource.rdbms.conn_postgresql import PostgreSQLConnector


def _connector(schema):
    """Build a connector without an engine, keeping the schema attribute."""
    conn = PostgreSQLConnector.__new__(PostgreSQLConnector)
    conn._schema = schema
    conn._engine = MagicMock()
    conn._engine.url.database = "postgres"
    conn._all_tables = set()
    # 这个实例不持有真实连接池，无需 close；同时避免析构函数访问未初始化的属性
    conn.close = lambda: None
    return conn


def _capture_session(rows, executed):
    """Return a session_scope yielding a session that records executed SQL."""

    @contextmanager
    def session_scope():
        session = MagicMock()

        def execute(statement, params=None):
            executed.append((str(statement), params))
            result = MagicMock()
            result.fetchall.return_value = rows
            return result

        session.execute.side_effect = execute
        yield session

    return session_scope


@pytest.mark.parametrize("schema", ["app", "public"])
def test_table_simple_info_scopes_to_configured_schema(schema):
    """The catalog walk is restricted to the connector's schema."""
    conn = _connector(schema)
    executed = []
    conn.session_scope = _capture_session(
        [("orders", "id, amount, customer")], executed
    )

    rows = conn.table_simple_info()

    assert rows == [("orders", "id, amount, customer")]
    assert len(executed) == 1
    sql, params = executed[0]
    # 只能查询配置的 schema，不能再遍历库里所有非系统 schema
    assert "n.nspname = :schema" in sql
    assert "NOT LIKE 'pg_%'" not in sql
    assert params == {"schema": schema}


def test_table_simple_info_defaults_to_public():
    """A connector without an explicit schema reads the public schema."""
    conn = _connector(None)
    executed = []
    conn.session_scope = _capture_session([], executed)

    assert conn.table_simple_info() == []
    assert executed[0][1] == {"schema": "public"}
