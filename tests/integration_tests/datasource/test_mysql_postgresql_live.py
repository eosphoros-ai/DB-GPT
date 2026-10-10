"""Opt-in tests against disposable databases; CI supplies both service URLs."""

import os
import uuid

import pytest
from sqlalchemy import text

from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector
from dbgpt_ext.datasource.rdbms.conn_postgresql import PostgreSQLConnector


@pytest.fixture(
    params=[
        ("MYSQL_TEST_URL", MySQLConnector),
        ("POSTGRES_TEST_URL", PostgreSQLConnector),
    ]
)
def database(request):
    variable, connector_class = request.param
    url = os.getenv(variable)
    if not url:
        pytest.skip(f"{variable} is not configured")
    connector = connector_class.from_uri(url)
    name = "validation_" + uuid.uuid4().hex[:12]
    try:
        with connector.session_scope() as session:
            session.execute(
                text(
                    f"CREATE TABLE {name} "
                    "(id INTEGER PRIMARY KEY, label VARCHAR(80), amount INTEGER)"
                )
            )
            session.execute(
                text(f"INSERT INTO {name} VALUES (1, 'alpha', 11), (2, 'beta', 29)")
            )
        connector.close()
        connector = connector_class.from_uri(url)
        yield connector, name
    finally:
        with connector.session_scope() as session:
            session.execute(text(f"DROP TABLE IF EXISTS {name}"))
        connector.close()


def test_live_schema_and_query(database):
    connector, name = database
    assert name in connector.get_table_names()
    assert {column["name"] for column in connector.get_columns(name)} == {
        "id",
        "label",
        "amount",
    }
    rows = connector.run(f"SELECT label, amount FROM {name} ORDER BY id")
    assert list(rows[0]) == ["label", "amount"]
    assert [tuple(row) for row in rows[1:]] == [("alpha", 11), ("beta", 29)]


def test_live_updates_and_invalid_sql(database):
    connector, name = database
    with connector.session_scope() as session:
        session.execute(text(f"UPDATE {name} SET amount=31 WHERE id=2"))
    rows = connector.run(f"SELECT SUM(amount) AS total FROM {name}")
    assert int(rows[1][0]) == 42
    with pytest.raises(Exception):
        connector.run("SELECT * FROM validation_missing_table")
    assert int(connector.run("SELECT 7 AS value")[1][0]) == 7
