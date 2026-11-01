import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine

from dbgpt_app.openapi.api_v1.dashboard.temporal_discovery import (
    collect_temporal_evidence,
    dashboard_temporal_context,
    infer_temporal_format,
)
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector


def _connector(tmp_path, values, *, name="event_date", type_=String, hidden=False):
    engine = create_engine(f"sqlite:///{tmp_path / 'temporal.db'}")
    metadata = MetaData()
    source = Table("observations", metadata, Column(name, type_))
    if hidden:
        Table("private_events", metadata, Column("secret_date", String))
    metadata.create_all(engine)
    if values:
        with engine.begin() as connection:
            connection.execute(source.insert(), [{name: value} for value in values])
    connector = SQLiteConnector(engine)
    if hidden:
        # Simulate a connector exposing only its permitted table inventory.
        connector.get_table_names = lambda: ["observations"]
    return connector


def test_full_source_counts_distinguish_dates_from_months(tmp_path):
    values = [
        (date(2010, 2, 5) + timedelta(weeks=i)).strftime("%d-%m-%Y") for i in range(143)
    ]
    connector = _connector(tmp_path, values * 2 + [None])
    fact = collect_temporal_evidence(connector)["columns"][0]

    assert fact["storage_type"] == "VARCHAR"
    assert fact["observed_storage_types"] == ["null", "text"]
    assert fact["row_count"] == 287
    assert fact["null_count"] == 1
    assert fact["source_distinct_count"] == 143
    assert fact["inference"]["format"] == "DD-MM-YYYY"
    assert fact["inference"]["calendar_distinct_counts"] == {
        "year": 3,
        "month": 33,
        "day": 143,
    }
    assert len(fact["samples"]) == 5
    assert set(fact["samples"]).issubset(values)


@pytest.mark.parametrize(
    "values,format_,counts",
    [
        (["2024-01-31", "2025-01-01"], "YYYY-MM-DD", {"year": 2, "month": 2, "day": 2}),
        (["2024/01/31"], "YYYY/MM/DD", {"year": 1, "month": 1, "day": 1}),
        (["20240229"], "YYYYMMDD", {"year": 1, "month": 1, "day": 1}),
        (["01-31-2024", "02-01-2024"], "MM-DD-YYYY", {"year": 1, "month": 2, "day": 2}),
        (["31/01/2024"], "DD/MM/YYYY", {"year": 1, "month": 1, "day": 1}),
        (["01/31/2024"], "MM/DD/YYYY", {"year": 1, "month": 1, "day": 1}),
        (["2024-01", "2025-01"], "YYYY-MM", {"year": 2, "month": 2}),
        (["2024/01"], "YYYY/MM", {"year": 1, "month": 1}),
        ([2024, 2025], "YYYY", {"year": 2}),
        (
            ["2024-01-31T12:00:00Z", "2024-02-01 09:00:00+08:00"],
            "ISO-8601 datetime",
            {"year": 1, "month": 2, "day": 2},
        ),
    ],
)
def test_formats_are_inferred_from_values_not_dataset_name(values, format_, counts):
    result = infer_temporal_format(values, complete=True)
    assert result["status"] == "inferred"
    assert result["format"] == format_
    assert result["calendar_distinct_counts"] == counts


@pytest.mark.parametrize(
    "values,status",
    [
        ([], "unknown"),
        ([None], "unknown"),
        ([""], "unknown"),
        (["not a date"], "unknown"),
        (["2023-02-29"], "unknown"),
        (["01-02-2024", "02-03-2024"], "ambiguous"),
        (["31-01-2024", "01-31-2024"], "mixed_or_invalid"),
        (["2024-01-01", "bad"], "mixed_or_invalid"),
        (["2024-01-01", "2024-02"], "mixed_or_invalid"),
        ([1700000000], "unknown"),
    ],
)
def test_insufficient_or_ambiguous_values_never_invent_calendar_counts(values, status):
    result = infer_temporal_format(values, complete=True)
    assert result["status"] == status
    assert result["format"] is None
    assert result["calendar_distinct_counts"] is None


def test_truncated_domain_does_not_report_sample_count_as_source_periods(tmp_path):
    connector = _connector(tmp_path, ["2024-01-01", "2024-02-01", "2025-01-01"])
    fact = collect_temporal_evidence(connector, max_distinct=2)["columns"][0]
    assert fact["source_distinct_count"] == 3
    assert fact["distinct_domain_complete"] is False
    assert fact["inference"]["inference_scope"] == "bounded_sample"
    assert fact["inference"]["calendar_distinct_counts"] is None


def test_date_values_with_neutral_name_and_quoted_identifiers_are_discovered(tmp_path):
    connector = _connector(
        tmp_path, ["2024-02-29"], name='value"; DROP TABLE observations;--'
    )
    fact = collect_temporal_evidence(connector)["columns"][0]
    assert fact["status"] == "observed"
    assert fact["inference"]["format"] == "YYYY-MM-DD"
    assert list(connector.get_table_names()) == ["observations"]


def test_only_connector_allowed_tables_are_profiled(tmp_path):
    connector = _connector(tmp_path, ["2024-02-29"], hidden=True)
    facts = collect_temporal_evidence(connector)["columns"]
    assert {fact["table"] for fact in facts} == {"observations"}


def test_empty_typed_column_remains_candidate_without_a_guessed_format(tmp_path):
    connector = _connector(tmp_path, [], name="happened", type_=DateTime)
    fact = collect_temporal_evidence(connector)["columns"][0]
    assert fact["storage_type"] == "DATETIME"
    assert fact["source_distinct_count"] == 0
    assert fact["inference"]["status"] == "unknown"


def test_epoch_units_are_not_guessed(tmp_path):
    connector = _connector(tmp_path, [1700000000], name="timestamp", type_=Integer)
    fact = collect_temporal_evidence(connector)["columns"][0]
    assert fact["storage_type"] == "INTEGER"
    assert fact["inference"]["status"] == "unknown"


def test_budget_and_query_errors_are_evidence_gaps_not_rejections(
    tmp_path, monkeypatch
):
    connector = _connector(tmp_path, ["2024-01-01"])
    fact = collect_temporal_evidence(connector, budget_seconds=0)["columns"][0]
    assert fact["status"] == "unavailable"
    assert fact["reason"] == "TimeoutError"

    def broken(*args, **kwargs):
        raise RuntimeError("sensitive connection details must not enter the prompt")

    monkeypatch.setattr(connector, "query_ex", broken)
    result = collect_temporal_evidence(connector)
    assert result["columns"][0]["reason"] == "RuntimeError"
    assert "sensitive" not in json.dumps(result)


def test_unknown_dialect_does_not_execute_unbounded_queries():
    result = collect_temporal_evidence(SimpleNamespace(dialect="unsupported"))
    assert result["columns"] == []
    assert result["status"].startswith("unavailable")


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", ["生成经营看板", "[[confirm-dashboard:id]] 确认"])
async def test_plan_and_confirmation_both_receive_fresh_source_evidence(
    tmp_path, prompt
):
    connector = _connector(tmp_path, ["31-01-2024", "15-02-2024"])
    context = await dashboard_temporal_context(
        connector, enabled=True, user_input=prompt
    )
    assert '"format": "DD-MM-YYYY"' in context
    assert '"source_distinct_count": 2' in context
    assert '"month": 2' in context
    assert "不是 SQL 校验闸门" in context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,prompt",
    [
        (False, "普通问题"),
        (True, "[[dashboard-annotation:id]] [异常分析]"),
        (True, "[[dashboard-annotation:id]] [修改组件]"),
    ],
)
async def test_no_extra_discovery_in_annotations_or_non_dashboard_turns(
    enabled, prompt
):
    context = await dashboard_temporal_context(
        object(), enabled=enabled, user_input=prompt
    )
    assert context == ""
