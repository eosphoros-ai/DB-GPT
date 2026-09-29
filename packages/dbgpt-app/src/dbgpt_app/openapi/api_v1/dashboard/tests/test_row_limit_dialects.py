"""Validate dialect rendering and bindings, without claiming remote DB coverage."""

import sqlite3
from types import SimpleNamespace

import pytest
import sqlglot
from sqlglot import exp

from dbgpt_app.openapi.api_v1.dashboard.query_executor import DashboardQueryExecutor
from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardSchemaV1
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_app.openapi.api_v1.dashboard.sql_security import (
    DashboardSQLSecurityError,
    DashboardUnsupportedDialectError,
    apply_row_limit,
    bind_named_parameters,
    prepare_multi_select_sql,
    validate_read_only_sql,
)
from dbgpt_app.openapi.api_v1.dashboard.tests.test_federation import (
    FederationConnector,
    federation_schema,
)


@pytest.mark.parametrize("dialect", ["sqlite", "mysql", "postgres", "tsql", "oracle"])
@pytest.mark.parametrize("inner_limit", [None, 2, 999999])
def test_row_cap_preserves_bindings_order_and_smaller_user_limits(dialect, inner_limit):
    original = sqlglot.parse_one(
        "WITH src AS (SELECT amount FROM sales WHERE region = :region) "
        "SELECT amount FROM src ORDER BY amount DESC"
    )
    if inner_limit is not None:
        original = original.limit(inner_limit)
    # The application/SQLAlchemy contract uses :name on every connector.
    original = original.transform(
        lambda node: exp.Var(this=f":{node.this}")
        if isinstance(node, exp.Placeholder)
        else node
    )
    limited = apply_row_limit(original.sql(dialect=dialect), 3, dialect=dialect)
    parsed = sqlglot.parse_one(limited, read=dialect)
    cap = parsed.args["limit"]
    assert int((cap.expression or cap.args["count"]).this) == 4
    checked = validate_read_only_sql(limited, dialect=dialect)
    assert checked.parameters == {"region"}
    assert ":region" in limited and "@region" not in limited
    if dialect == "tsql":
        assert "TOP 4" in limited and "LIMIT" not in limited
        assert parsed.args.get("with") is not None
        for select in parsed.find_all(exp.Select):
            if select.args.get("order"):
                assert select.args.get("limit") or select.args.get("offset")
    if dialect == "oracle":
        assert "FETCH FIRST 4 ROWS ONLY" in limited
        assert "AS dbgpt_dashboard_query" not in limited

    # Run equivalent SQLite SQL to check row semantics and parameter handling.
    # Native SQL Server/Oracle execution requires separately configured servers.
    equivalent = parsed.sql(dialect="sqlite")
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE sales (region TEXT, amount INTEGER)")
        connection.executemany(
            "INSERT INTO sales VALUES (?, ?)", [("North", n) for n in range(8)]
        )
        rows = connection.execute(equivalent, {"region": "North"}).fetchall()
        assert rows == [(n,) for n in range(7, 7 - min(inner_limit or 4, 4), -1)]
        assert (
            connection.execute(equivalent, {"region": "' OR 1=1 --"}).fetchall() == []
        )


@pytest.mark.parametrize("dialect", ["sqlite", "mysql", "postgres", "tsql", "oracle"])
def test_multi_select_rendering_keeps_sqlalchemy_bind_names(dialect):
    sql, values = prepare_multi_select_sql(
        "SELECT amount FROM sales WHERE region IN (:regions)",
        {"regions": ["North", "South"]},
        {"regions"},
        dialect=dialect,
    )
    checked = validate_read_only_sql(sql, dialect=dialect)
    bound_sql, bound = bind_named_parameters(sql, values, checked.parameters)
    limited = apply_row_limit(bound_sql, 10, dialect=dialect)
    assert validate_read_only_sql(limited, dialect=dialect).parameters == set(bound)
    assert "@regions" not in limited


@pytest.mark.parametrize(
    "db_type,expected",
    [
        ("mssql", "tsql"),
        ("sqlserver", "tsql"),
        ("oracle", "oracle"),
        ("postgresql", "postgres"),
        ("mariadb", "mysql"),
        ("  PostgreSQL  ", "postgres"),
        ("SQLSERVER", "tsql"),
    ],
)
def test_connector_dialect_aliases(db_type, expected):
    assert DashboardQueryExecutor._dialect(SimpleNamespace(db_type=db_type)) == expected


@pytest.mark.parametrize("maximum,expected", [(-1, 2), (0, 2), (500000, 5001)])
def test_row_cap_clamps_server_bounds(maximum, expected):
    limited = apply_row_limit("SELECT amount FROM sales", maximum, dialect="tsql")
    assert (
        int(sqlglot.parse_one(limited, read="tsql").args["limit"].expression.this)
        == expected
    )


@pytest.mark.parametrize(
    "db_type", ["vertica", "maxcompute", "gaussdb", "openGauss", "oceanbase"]
)
@pytest.mark.parametrize("federated", [False, True])
def test_unsupported_data_source_has_clear_non_retryable_error_before_execution(
    db_type, federated
):
    connectors = {
        name: FederationConnector("sales", ["month", "amount"], [("01", 10)])
        for name in ("north-db", "south-db")
    }
    for connector in connectors.values():
        connector.db_type = db_type
    raw = federation_schema()
    if not federated:
        raw["widgets"][0]["query"].pop("federation")
        raw["widgets"][0]["query"]["sql"] = "SELECT month, amount AS sales FROM sales"
    schema = DashboardSchemaV1.model_validate(raw)
    executor = DashboardQueryExecutor(connector_resolver=connectors.__getitem__)
    validation = executor.validate_schema(schema)
    assert not validation.valid
    assert any(issue.code == "unsupported_data_source" for issue in validation.issues)
    result = executor.execute_widget(schema, "regional-sales", {})
    assert result.error is not None
    assert result.error.code == "unsupported_data_source"
    assert result.error.retryable is False
    assert db_type.lower() in result.error.message
    assert "Choose a supported data source" in result.error.message
    assert "SQL cannot be parsed" not in result.error.message
    assert all(not connector.calls for connector in connectors.values())


@pytest.mark.parametrize(
    "dialect", ["vertica", "maxcompute", "gaussdb", "opengauss", "oceanbase"]
)
def test_direct_sql_helpers_distinguish_unknown_dialect_from_invalid_sql(dialect):
    sql = "SELECT amount FROM sales WHERE region IN (:regions)"
    with pytest.raises(DashboardUnsupportedDialectError):
        validate_read_only_sql(sql, dialect=dialect)
    with pytest.raises(DashboardUnsupportedDialectError):
        prepare_multi_select_sql(
            sql, {"regions": ["North"]}, {"regions"}, dialect=dialect
        )
    with pytest.raises(DashboardUnsupportedDialectError):
        apply_row_limit(sql, 5, dialect=dialect)


def test_row_cap_does_not_accept_unrecognized_dialect_or_multiple_statements():
    with pytest.raises(DashboardSQLSecurityError):
        apply_row_limit("SELECT 1", 3, dialect="unregistered_database")
    with pytest.raises(DashboardSQLSecurityError):
        apply_row_limit("SELECT 1; DELETE FROM sales", 3, dialect="tsql")


@pytest.mark.parametrize("db_type,dialect", [("mssql", "tsql"), ("oracle", "oracle")])
@pytest.mark.parametrize("federated", [False, True])
def test_widget_and_federated_execution_pass_connector_dialect(
    db_type, dialect, federated
):
    connectors = {
        name: FederationConnector(
            "sales", ["month", "amount"], [("01", 10), ("02", 20), ("03", 30)]
        )
        for name in ("north-db", "south-db")
    }
    for connector in connectors.values():
        connector.db_type = db_type
    raw = federation_schema()
    if not federated:
        raw["widgets"][0]["query"] = {
            "data_source_id": "north-db",
            "sql": (
                "SELECT month, amount FROM sales "
                "WHERE month >= :start_month ORDER BY month"
            ),
            "default_parameters": {"start_month": "01"},
            "max_rows": 2,
            "output_fields": [
                {"name": "month", "type": "string"},
                {"name": "amount", "type": "number"},
            ],
        }
        raw["widgets"][0]["encoding"] = {"x": "month", "y": "amount"}
    schema = DashboardSchemaV1.model_validate(raw)
    service = DashboardService(connector_resolver=connectors.__getitem__)
    result = service.validate_widget_query(schema, "regional-sales")
    assert result.error is None
    assert result.truncated is True
    selected = connectors.values() if federated else [connectors["north-db"]]
    for connector in selected:
        assert len(connector.calls) == 1
        query = connector.calls[0]
        assert query["params"] == {"start_month": "01"}
        assert ("TOP 3" if dialect == "tsql" else "FETCH FIRST 3 ROWS ONLY") in query[
            "sql"
        ]
        assert "LIMIT" not in query["sql"]
        validate_read_only_sql(query["sql"], dialect=dialect)
