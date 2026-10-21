import json

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
