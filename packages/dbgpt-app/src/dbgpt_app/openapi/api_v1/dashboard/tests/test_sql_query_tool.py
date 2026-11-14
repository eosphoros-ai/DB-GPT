import json
import sqlite3
from datetime import datetime

from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query


class _Connector:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, _sql: str):
        self.calls += 1
        return [[("value",)], [self.calls]]


def test_dashboard_sql_query_limit_is_enforced_before_connector_execution():
    connector = _Connector()
    sql_query = make_sql_query({}, connector, max_calls=2)

    first = json.loads(sql_query(sql="SELECT 1"))
    second = json.loads(sql_query(sql="SELECT 2"))
    limited = json.loads(sql_query(sql="SELECT 3"))

    assert first["chunks"][1]["output_type"] == "markdown"
    assert second["chunks"][1]["output_type"] == "markdown"
    assert connector.calls == 2
    assert limited["dashboard_discovery_limit_reached"] is True
    assert "call plan_dashboard now" in limited["chunks"][0]["content"]


def test_sql_query_emits_query_artifact_chunk_with_result_set():
    connector = _Connector()
    sql_query = make_sql_query({}, connector)

    envelope = json.loads(sql_query(sql="SELECT value FROM t"))

    query_chunk = envelope["chunks"][0]
    assert query_chunk["output_type"] == "query"
    payload = query_chunk["content"]
    assert payload["sql"] == "SELECT value FROM t"
    assert payload["columns"] == ["value"]
    assert payload["rows"] == [[1]]
    assert payload["row_count"] == 1
    assert payload["truncated"] is False
    # The markdown observation for the model still follows the artifact.
    assert envelope["chunks"][1]["output_type"] == "markdown"
    assert "| value |" in envelope["chunks"][1]["content"]


def test_sql_query_rejects_write_statements_without_touching_connector():
    connector = _Connector()
    sql_query = make_sql_query({}, connector)

    denied = json.loads(sql_query(sql="DELETE FROM t"))

    assert connector.calls == 0
    assert denied["chunks"][0]["output_type"] == "text"
    assert "DELETE" in denied["chunks"][0]["content"]


def test_zero_limit_blocks_sql_on_dashboard_confirmation_turns():
    connector = _Connector()
    sql_query = make_sql_query({}, connector, max_calls=0)

    limited = json.loads(sql_query(sql="SELECT 1"))

    assert connector.calls == 0
    assert limited["dashboard_discovery_limit_reached"] is True


class _SqliteConnector:
    def run(self, sql: str):
        with sqlite3.connect(":memory:") as connection:
            cursor = connection.execute(sql)
            return [cursor.description, *cursor.fetchall()]


def test_query_execution_record_matches_real_sqlite_result():
    query = make_sql_query({"database_name": "test_db"}, _SqliteConnector())
    payload = json.loads(query(sql="SELECT 42 AS answer"))["chunks"][0]["content"]
    assert payload["db_name"] == "test_db"
    assert payload["columns"] == ["answer"]
    assert payload["rows"] == [[42]]
    record = payload["execution"]
    assert record["status"] == "succeeded"
    assert record["tool"] == "sql_query"
    assert record["duration_ms"] >= 0
    assert datetime.fromisoformat(record["started_at"]).tzinfo is not None


def test_empty_query_still_has_sql_result_and_execution_record():
    query = make_sql_query({"database_name": "test_db"}, _SqliteConnector())
    payload = json.loads(query(sql="SELECT 42 AS answer WHERE 0"))["chunks"][0][
        "content"
    ]
    assert payload["columns"] == ["answer"]
    assert payload["rows"] == []
    assert payload["row_count"] == 0
    assert payload["execution"]["status"] == "succeeded"


def test_connector_with_no_result_still_emits_query_artifact():
    class EmptyConnector:
        def run(self, sql):
            return None

    query = make_sql_query({}, EmptyConnector())
    payload = json.loads(query(sql="SELECT 1"))["chunks"][0]["content"]
    assert payload["rows"] == []
    assert payload["columns"] == []
    assert payload["execution"]["status"] == "succeeded"


def test_failed_query_emits_attempt_record_without_successful_result():
    query = make_sql_query({"database_name": "test_db"}, _SqliteConnector())
    envelope = json.loads(query(sql="SELECT * FROM missing_table"))
    assert envelope["success"] is False
    payload = envelope["chunks"][1]["content"]
    assert payload["sql"] == "SELECT * FROM missing_table"
    assert payload["execution"]["status"] == "failed"
    assert "missing_table" in payload["execution"]["error"]
    assert payload["rows"] == []
