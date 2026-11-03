"""Execute SQLite date mistakes and verify that generation requests a repair."""

import sqlite3
from datetime import datetime

import pytest

from dbgpt_app.openapi.api_v1.dashboard.planner import (
    DashboardPlannerService,
    _reject_invalid_line_axis,
    _reject_null_table_period,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardPlan,
    DashboardPublicationBinding,
    DashboardQueryDraftRequest,
    DashboardWidget,
    WidgetQueryResult,
)

from .test_annotations import annotation_services as _annotation_services_fixture

annotation_services = _annotation_services_fixture


def _query(sql):
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE sales (day TEXT, revenue REAL)")
        connection.executemany(
            "INSERT INTO sales VALUES (?, ?)",
            [("31-12-2010", 10), ("14-01-2011", 20), ("07-01-2011", 30)],
        )
        cursor = connection.execute(sql)
        rows = [list(row) for row in cursor.fetchall()]
    return WidgetQueryResult(
        widget_id="trend",
        columns=[field[0] for field in cursor.description],
        rows=rows,
        row_count=len(rows),
        refreshed_at=datetime.now(),
    )


def _widget():
    return DashboardWidget(
        id="trend",
        type="line",
        title="Revenue",
        query={"data_source_id": "retail", "sql": "SELECT day, revenue FROM sales"},
        encoding={"x": "week", "y": "sales"},
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT strftime('%Y-W%W', day) AS week, SUM(revenue) AS sales "
        "FROM sales GROUP BY week ORDER BY week",
        "SELECT day AS week, SUM(revenue) AS sales "
        "FROM sales GROUP BY day ORDER BY day",
        "SELECT MIN(day) AS week, SUM(revenue) AS sales FROM sales",
    ],
)
def test_executable_sql_with_broken_date_axis_requires_repair(sql):
    result = _query(sql)
    checked = _reject_invalid_line_axis(result, _widget())
    assert checked.error.code == "planner_widget_invalid_time_axis"
    assert checked.error.retryable
    assert checked.rows == result.rows
    assert result.error is None


def test_normalized_calendar_axis_keeps_real_rows_in_order():
    result = _query(
        "SELECT substr(day,7,4)||'-'||substr(day,4,2)||'-'||substr(day,1,2) AS week, "
        "SUM(revenue) AS sales FROM sales GROUP BY week ORDER BY week"
    )
    assert _reject_invalid_line_axis(result, _widget()).error is None
    assert result.rows == [
        ["2010-12-31", 10],
        ["2011-01-07", 30],
        ["2011-01-14", 20],
    ]


@pytest.mark.parametrize("normalized", [False, True])
def test_table_time_groups_require_real_periods(normalized):
    expression = (
        "substr(day,7,4)||'-'||substr(day,4,2)||'-'||substr(day,1,2)"
        if normalized
        else "date(day)"
    )
    result = _query(
        f"SELECT {expression} AS week, SUM(revenue) AS sales FROM sales GROUP BY week"
    )
    widget = _widget().model_copy(
        update={
            "type": "table",
            "publication": None,
        }
    )
    widget.publication = DashboardPublicationBinding(
        query=widget.query, group_by=["week"]
    )
    checked = _reject_null_table_period(result, widget)
    assert (checked.error is None) == normalized
    widget.publication.row_mode = True
    assert _reject_null_table_period(result, widget).error is None


def test_categorical_line_axis_is_not_treated_as_a_date():
    result = _query("SELECT 'First' AS week, SUM(revenue) AS sales FROM sales")
    assert _reject_invalid_line_axis(result, _widget()).error is None


def test_partially_parseable_axis_cannot_hide_sales_in_a_null_bucket():
    result = _query(
        "SELECT strftime('%Y-W%W', day) AS week, SUM(revenue) AS sales "
        "FROM sales GROUP BY week"
    )
    result.rows.append(["2011-W01", 5])
    result.row_count += 1
    assert _reject_invalid_line_axis(result, _widget()).error is not None


@pytest.mark.asyncio
async def test_create_and_repair_both_reject_real_sqlite_null_date_axis(
    annotation_services, monkeypatch
):
    service = annotation_services[1]
    monkeypatch.setattr(
        annotation_services[3],
        "get_fields",
        lambda *_args: [("day", "string"), ("revenue", "number")],
    )

    def execute(sql, params=None, timeout=None):
        result = _query(sql)
        return result.columns, result.rows

    monkeypatch.setattr(annotation_services[3], "query_ex", execute)
    planner = DashboardPlannerService(service)
    plan = DashboardPlan(
        title="Weekly sales",
        business_theme="Retail",
        audience="Operations",
        decision_goal="Monitor weekly revenue",
        metrics=["revenue"],
        widgets=[
            {
                "id": "trend",
                "type": "line",
                "title": "Weekly revenue",
                "business_question": "How does revenue change?",
                "metric": "revenue",
                "dimensions": ["day"],
                "analysis_level": 1,
                "rationale": "Weekly trend",
                "layout": {"width": "full", "height": "standard"},
            }
        ],
    )
    saved = await planner.create_plan_draft(
        plan=plan,
        data_source_id="demo",
        owner_id="alice",
        conversation_id="time-axis",
        prompt="Weekly trend",
        model_name="offline",
        request_token="plan",
    )
    broken_sql = (
        "SELECT MIN(day) AS week, SUM(revenue) AS sales "
        "FROM sales GROUP BY strftime('%Y-W%W', day)"
    )

    def request(sql, revision):
        return DashboardQueryDraftRequest(
            expected_revision=revision,
            widgets=[
                {
                    "widget_id": "trend",
                    "sql": sql,
                    "output_fields": [
                        {"name": "week", "type": "string"},
                        {"name": "sales", "type": "number"},
                    ],
                    "encoding": {"x": "week", "y": "sales"},
                }
            ],
        )

    failed, _ = await planner.complete_plan_draft(
        dashboard_id=saved.id,
        query_request=request(broken_sql, saved.current_revision),
        owner_id="alice",
        request_token="confirmed",
    )
    assert failed.schema_payload.widgets[0].error is not None
    assert failed.schema_payload.widgets[0].type == "line"
    still_failed, _ = await planner.repair_draft(
        dashboard_id=saved.id,
        plan=plan,
        query_request=request(broken_sql, failed.current_revision),
        owner_id="alice",
    )
    assert still_failed.schema_payload.widgets[0].error is not None
    normalized_sql = (
        "SELECT substr(day,7,4)||'-'||substr(day,4,2)||'-'||substr(day,1,2) AS week, "
        "SUM(revenue) AS sales FROM sales GROUP BY week ORDER BY week"
    )
    repaired, results = await planner.repair_draft(
        dashboard_id=saved.id,
        plan=plan,
        query_request=request(normalized_sql, still_failed.current_revision),
        owner_id="alice",
    )
    assert repaired.schema_payload.widgets[0].error is None
    assert results["trend"].row_count == 3
