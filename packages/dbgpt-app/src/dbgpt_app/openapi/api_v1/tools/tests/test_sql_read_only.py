"""Read-only SQL boundary for the model-facing SQL tools."""

import json
import sqlite3

import pytest

from dbgpt_app.openapi.api_v1.tools.chart_query import make_chart_query
from dbgpt_app.openapi.api_v1.tools.sql_read_only import (
    ReadOnlySqlError,
    read_only_sql,
)
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

CTE_WRITE = "WITH chosen AS (SELECT 1)\nDELETE FROM accounts\nRETURNING id;"


@pytest.mark.parametrize(
    "sql",
    [
        CTE_WRITE,
        "WITH chosen AS (SELECT 1) UPDATE accounts SET balance = 0",
        "WITH chosen AS (SELECT 1) INSERT INTO accounts(id, balance) SELECT 1, 0",
        "WITH removed AS (DELETE FROM accounts RETURNING id) SELECT * FROM removed",
        "WITH changed AS (UPDATE accounts SET balance = 0 RETURNING id) "
        "SELECT * FROM changed",
        "SELECT * INTO backup FROM accounts",
        "SELECT * FROM accounts INTO OUTFILE '/tmp/accounts.csv'",
        "SELECT 1; DELETE FROM accounts",
        "EXPLAIN DELETE FROM accounts",
        "DROP TABLE accounts",
        "",
    ],
)
def test_rejects_non_read_only_statements(sql):
    with pytest.raises(ReadOnlySqlError):
        read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM accounts",
        "WITH chosen AS (SELECT 1) SELECT * FROM chosen",
        "WITH RECURSIVE chosen AS (SELECT 1) SELECT * FROM chosen",
        "EXPLAIN QUERY PLAN SELECT * FROM accounts",
        "select `id` from accounts;",
        "SELECT 'DELETE FROM accounts; INTO backup' AS description",
        'SELECT "delete", "into" FROM accounts -- DELETE FROM accounts',
    ],
)
def test_accepts_single_read_only_statement(sql):
    assert read_only_sql(sql)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        CTE_WRITE,
        "WITH chosen AS (SELECT 1) UPDATE accounts SET balance = 0 RETURNING id",
        "WITH chosen AS (SELECT 1) INSERT INTO accounts VALUES (3, 0) RETURNING id",
        "SELECT 1; DELETE FROM accounts",
    ],
)
async def test_chart_query_rejects_cte_write_without_touching_sqlite(tmp_path, sql):
    database_path = tmp_path / "accounts.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER)"
        )
        connection.executemany(
            "INSERT INTO accounts (id, balance) VALUES (?, ?)",
            [(1, 100), (2, 200)],
        )
        connection.commit()

    connector = SQLiteConnector.from_file_path(str(database_path))
    try:
        chart_query = make_chart_query({}, connector)
        payload = json.loads(await chart_query(sql=sql, display_type="response_table"))
    finally:
        connector.close()

    assert payload["success"] is False
    assert payload["error_code"] == "SQL_READ_ONLY_REQUIRED"

    with sqlite3.connect(database_path) as connection:
        remaining = connection.execute(
            "SELECT id, balance FROM accounts ORDER BY id"
        ).fetchall()
    assert remaining == [(1, 100), (2, 200)]
