from copy import deepcopy

import pytest

from dbgpt_app.openapi.api_v1.dashboard.federation import (
    DashboardFederationService,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAction,
    DashboardSchemaV1,
    collect_schema_issues,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService


class FederationConnector:
    db_type = "sqlite"

    def __init__(self, table, columns, rows):
        self.table = table
        self.columns = columns
        self.rows = rows
        self.calls = []

    def get_table_names(self):
        return [self.table]

    def get_fields(self, table, database=None):
        return [(name, "text") for name in self.columns]

    def query_ex(self, sql, params=None, timeout=None):
        self.calls.append({"sql": sql, "params": params, "timeout": timeout})
        return self.columns, self.rows


def federation_schema(mode="union_all"):
    sources = [
        {
            "alias": "north",
            "data_source_id": "north-db",
            "sql": "SELECT month, amount FROM sales WHERE month >= :start_month",
            "default_parameters": {"start_month": "01"},
            "column_mapping": {"month": "month", "amount": "sales"},
            "max_rows": 2,
        },
        {
            "alias": "south",
            "data_source_id": "south-db",
            "sql": "SELECT month, amount FROM sales WHERE month >= :start_month",
            "default_parameters": {"start_month": "01"},
            "column_mapping": {"month": "month", "amount": "sales"},
            "max_rows": 2,
        },
    ]
    query = {
        "data_source_id": "north-db",
        "federation": {
            "mode": mode,
            "sources": sources,
            "max_output_rows": 3,
        },
        "output_fields": [
            {"name": "month", "type": "string"},
            {"name": "sales", "type": "number"},
        ],
    }
    return {
        "schema_version": "1.1",
        "dashboard": {
            "title": "Federated sales",
            "data_source_id": "north-db",
        },
        "widgets": [
            {
                "id": "regional-sales",
                "type": "line",
                "title": "Regional sales",
                "query": query,
                "encoding": {"x": "month", "y": "sales"},
            }
        ],
        "layouts": {
            "desktop": [
                {"widget_id": "regional-sales", "x": 0, "y": 0, "w": 12, "h": 5}
            ]
        },
    }


def test_union_all_executes_each_source_with_independent_limits():
    connectors = {
        "north-db": FederationConnector(
            "sales", ["month", "amount"], [("01", 10), ("02", 20), ("03", 30)]
        ),
        "south-db": FederationConnector(
            "sales", ["month", "amount"], [("01", 40), ("02", 50)]
        ),
    }
    service = DashboardService(connector_resolver=connectors.__getitem__)
    schema = DashboardSchemaV1.model_validate(federation_schema())

    result = service.validate_widget_query(schema, "regional-sales")

    assert result.error is None
    assert result.columns == ["month", "sales"]
    assert result.rows == [["01", 10], ["02", 20], ["01", 40]]
    assert result.truncated is True
    assert connectors["north-db"].calls[0]["params"] == {"start_month": "01"}
    assert "LIMIT 3" in connectors["north-db"].calls[0]["sql"]


def test_federation_column_mapping_is_case_insensitive():
    connectors = {
        "north-db": FederationConnector("sales", ["MONTH", "AMOUNT"], [("01", 10)]),
        "south-db": FederationConnector("sales", ["Month", "Amount"], [("02", 20)]),
    }
    service = DashboardService(connector_resolver=connectors.__getitem__)
    schema = DashboardSchemaV1.model_validate(federation_schema())

    result = service.validate_widget_query(schema, "regional-sales")

    assert result.error is None
    assert result.rows == [["01", 10], ["02", 20]]


def test_inner_and_left_join_use_mapped_equality_keys():
    payload = federation_schema("join")
    payload["widgets"][0]["type"] = "table"
    payload["widgets"][0]["encoding"] = {"columns": ["store", "sales", "target"]}
    payload["widgets"][0]["query"]["output_fields"] = [
        {"name": "store", "type": "string"},
        {"name": "sales", "type": "number"},
        {"name": "target", "type": "number", "nullable": True},
    ]
    payload["widgets"][0]["query"]["federation"] = {
        "mode": "join",
        "sources": [
            {
                "alias": "actual",
                "data_source_id": "actual-db",
                "sql": "SELECT store_id, amount FROM sales",
                "column_mapping": {"store_id": "store", "amount": "sales"},
            },
            {
                "alias": "plan",
                "data_source_id": "plan-db",
                "sql": "SELECT store_id, target FROM targets",
                "column_mapping": {"store_id": "store", "target": "target"},
            },
        ],
        "join": {
            "left_alias": "actual",
            "right_alias": "plan",
            "left_field": "store",
            "right_field": "store",
            "join_type": "inner",
        },
        "max_output_rows": 10,
    }
    payload["widgets"][0]["query"]["data_source_id"] = "actual-db"
    payload["dashboard"]["data_source_id"] = "actual-db"
    connectors = {
        "actual-db": FederationConnector(
            "sales", ["store_id", "amount"], [("A", 100), ("B", 200)]
        ),
        "plan-db": FederationConnector("targets", ["store_id", "target"], [("A", 90)]),
    }
    service = DashboardService(connector_resolver=connectors.__getitem__)
    schema = DashboardSchemaV1.model_validate(payload)

    inner = service.validate_widget_query(schema, "regional-sales")
    assert inner.rows == [["A", 100, 90]]

    left_payload = deepcopy(payload)
    left_payload["widgets"][0]["query"]["federation"]["join"]["join_type"] = "left"
    left = service.validate_widget_query(
        DashboardSchemaV1.model_validate(left_payload), "regional-sales"
    )
    assert left.rows == [["A", 100, 90], ["B", 200, None]]


def test_federated_source_sql_is_validated_before_execution():
    payload = federation_schema()
    payload["widgets"][0]["query"]["federation"]["sources"][1]["sql"] = (
        "DELETE FROM sales"
    )
    connectors = {
        source_id: FederationConnector("sales", ["month", "amount"], [])
        for source_id in ("north-db", "south-db")
    }
    service = DashboardService(connector_resolver=connectors.__getitem__)

    result = service.validate_schema(DashboardSchemaV1.model_validate(payload))

    assert result.valid is False
    assert "query_validation_failed" in {issue.code for issue in result.issues}
    assert connectors["south-db"].calls == []


def test_schema_1_0_cannot_silently_enable_federation():
    payload = federation_schema()
    payload["schema_version"] = "1.0"
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "federation_requires_schema_1_1" in {issue.code for issue in issues}


def test_invalid_federation_is_not_executed_during_validation():
    payload = federation_schema()
    payload["schema_version"] = "1.0"
    connectors = {
        source_id: FederationConnector("sales", ["month", "amount"], [])
        for source_id in ("north-db", "south-db")
    }
    service = DashboardService(connector_resolver=connectors.__getitem__)

    result = service.validate_schema(
        DashboardSchemaV1.model_validate(payload), execute_queries=True
    )

    assert result.widget_status["regional-sales"] == "invalid"
    assert all(connector.calls == [] for connector in connectors.values())


def test_query_authorization_receives_every_federated_source():
    class CapturingAuthorization:
        def __init__(self):
            self.source_ids = None

        def require(self, dashboard_id, actor_id, action, *, data_source_ids=None):
            self.source_ids = data_source_ids
            return object()

    authorization = CapturingAuthorization()
    service = DashboardService(dao=object(), authorization_service=authorization)
    schema = DashboardSchemaV1.model_validate(federation_schema())

    service.require_permission("dashboard", "alice", DashboardAction.QUERY, schema)

    assert set(authorization.source_ids) == {"north-db", "south-db"}


def test_federation_rejects_total_input_rows_before_join_or_union():
    schema = DashboardSchemaV1.model_validate(federation_schema())
    federation = schema.widgets[0].query.federation
    assert federation is not None

    with pytest.raises(ValueError, match="total row limit"):
        DashboardFederationService(max_input_rows=1).combine(
            federation,
            {
                "north": [{"month": "01", "sales": 10}],
                "south": [{"month": "02", "sales": 20}],
            },
            ["month", "sales"],
        )


def test_federation_rejects_total_input_bytes_before_join_or_union():
    schema = DashboardSchemaV1.model_validate(federation_schema())
    federation = schema.widgets[0].query.federation
    assert federation is not None

    with pytest.raises(ValueError, match="in-memory byte limit"):
        DashboardFederationService(max_input_bytes=32).combine(
            federation,
            {
                "north": [{"month": "01", "sales": "x" * 100}],
                "south": [],
            },
            ["month", "sales"],
        )
