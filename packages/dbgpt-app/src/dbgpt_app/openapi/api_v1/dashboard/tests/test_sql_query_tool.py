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

    assert first["chunks"][0]["output_type"] == "markdown"
    assert second["chunks"][0]["output_type"] == "markdown"
    assert connector.calls == 2
    assert limited["dashboard_discovery_limit_reached"] is True
    assert "call plan_dashboard now" in limited["chunks"][0]["content"]


def test_zero_limit_blocks_sql_on_dashboard_confirmation_turns():
    connector = _Connector()
    sql_query = make_sql_query({}, connector, max_calls=0)

    limited = json.loads(sql_query(sql="SELECT 1"))

    assert connector.calls == 0
    assert limited["dashboard_discovery_limit_reached"] is True
