import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.dashboard.chart_selection import (
    normalize_executed_chart,
    normalize_plan_chart_selection,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardPlan,
    DashboardSchemaV1,
    WidgetQueryResult,
    collect_schema_issues,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService

from .test_service import FakeConnector, FakeDao


def plan(count=None, dimensions=None):
    return DashboardPlan.model_validate(
        {
            "title": "Financial review",
            "business_theme": "Financial review",
            "metrics": ["Revenue"],
            "widgets": [
                {
                    "id": "trend",
                    "type": "line",
                    "title": "Revenue",
                    "business_question": "Compare revenue",
                    "metric": "Revenue",
                    "dimensions": dimensions or [],
                    "expected_data_points": count,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "count,expected",
    [(1, "kpi"), (2, "bar"), (3, "bar"), (4, "line"), (0, "line"), (None, "line")],
)
def test_deterministic_planning_boundaries(count, expected):
    original = plan(count)
    normalized = normalize_plan_chart_selection(original)
    assert normalized.widgets[0].type.value == expected
    assert original.widgets[0].type.value == "line"
    if expected != "line":
        assert "small-series" in normalized.widgets[0].rationale


def test_source_count_overrides_model_guess_only_when_proving_small_domain():
    evidence = {
        "columns": [
            {
                "table": "financial",
                "column": "fiscal_year",
                "status": "observed",
                "distinct_domain_complete": True,
                "source_distinct_count": 3,
            }
        ]
    }
    normalized = normalize_plan_chart_selection(plan(99, ["fiscal_year"]), evidence)
    assert normalized.widgets[0].type.value == "bar"
    assert normalized.widgets[0].expected_data_points == 3
    evidence["columns"][0]["source_distinct_count"] = 143
    assert (
        normalize_plan_chart_selection(plan(33, ["fiscal_year"]), evidence)
        .widgets[0]
        .expected_data_points
        == 33
    )


def test_ambiguous_or_incomplete_source_evidence_does_not_guess():
    fact = {
        "table": "financial",
        "column": "fiscal_year",
        "status": "observed",
        "distinct_domain_complete": False,
        "source_distinct_count": 3,
    }
    assert (
        normalize_plan_chart_selection(plan(None, ["fiscal_year"]), {"columns": [fact]})
        .widgets[0]
        .type.value
        == "line"
    )
    fact["distinct_domain_complete"] = True
    assert (
        normalize_plan_chart_selection(
            plan(None, ["fiscal_year"]),
            {"columns": [fact, {**fact, "table": "another"}]},
        )
        .widgets[0]
        .type.value
        == "line"
    )


def chart(rows, *, area=False):
    schema = DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.4",
            "dashboard": {
                "title": "Finance",
                "data_source_id": "financial",
                "theme": {"preset": "clarity", "mode": "light"},
            },
            "widgets": [
                {
                    "id": "trend",
                    "type": "line",
                    "title": "Revenue",
                    "query": {
                        "data_source_id": "financial",
                        "sql": "SELECT fiscal_year, revenue FROM financial",
                        "output_fields": [
                            {"name": "fiscal_year", "type": "number"},
                            {"name": "revenue", "type": "number"},
                        ],
                    },
                    "encoding": {"x": "fiscal_year", "y": "revenue"},
                    "presentation": {"visualization": "area" if area else "line"},
                }
            ],
            "layouts": {
                "desktop": [{"widget_id": "trend", "x": 0, "y": 0, "w": 6, "h": 5}]
            },
            "metadata": {
                "compatibility": {
                    "dashboard_plan": plan().model_dump(),
                    "agent_dashboard_workflow": {"plan": plan().model_dump()},
                }
            },
        }
    )
    result = WidgetQueryResult(
        widget_id="trend",
        columns=["fiscal_year", "revenue"],
        rows=rows,
        row_count=len(rows),
        refreshed_at=datetime.now(),
    )
    return schema, schema.widgets[0], result


@pytest.mark.parametrize(
    "count,expected", [(1, "kpi"), (2, "bar"), (3, "bar"), (4, "line")]
)
@pytest.mark.parametrize("area", [False, True])
def test_actual_trial_rows_override_line_or_area(count, expected, area):
    schema, widget, result = chart(
        [[2020 + i, 100 + i] for i in range(count)], area=area
    )
    normalize_executed_chart(schema, widget, result)
    assert widget.type.value == expected
    assert not collect_schema_issues(schema)
    if count <= 3:
        for planned in [
            schema.metadata.compatibility["dashboard_plan"],
            schema.metadata.compatibility["agent_dashboard_workflow"]["plan"],
        ]:
            assert planned["widgets"][0]["type"] == expected
            assert "真实试运行" in planned["widgets"][0]["rationale"]


def test_long_form_counts_categories_not_series_rows():
    schema, widget, result = chart(
        [[2022 + year, 100 + series] for year in range(3) for series in range(3)]
    )
    assert len(result.rows) == 9
    assert normalize_executed_chart(schema, widget, result)
    assert widget.type.value == "bar"
    assert "3 个数据点" in widget.description


@pytest.mark.parametrize(
    "rows,truncated", [([], False), ([[None, 100]], False), ([[2024, 100]], True)]
)
def test_incomplete_trial_cannot_establish_cardinality(rows, truncated):
    schema, widget, result = chart(rows)
    result.truncated = truncated
    assert not normalize_executed_chart(schema, widget, result)


@pytest.mark.asyncio
async def test_plan_is_normalized_before_confirmation_event_and_save():
    service = DashboardService(
        dao=FakeDao(), connector_resolver=lambda _: FakeConnector()
    )
    events = []
    record = await DashboardPlannerService(service).create_plan_draft(
        plan=plan(3, ["fiscal_year"]),
        data_source_id="financial",
        owner_id="alice",
        conversation_id="selection",
        prompt="Three annual periods",
        model_name="offline",
        request_token="plan-turn",
        event_callback=lambda name, payload: events.append((name, payload)),
    )
    assert record.schema_payload.widgets[0].type.value == "bar"
    assert record.schema_payload.widgets[0].error.code == "query_not_generated"
    assert events[-1][1]["plan"]["widgets"][0]["type"] == "bar"


def test_apple_old_snapshot_remains_byte_identical_while_new_buffer_is_normalized():
    root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "examples/dashboard").exists()
    )
    source = root / "examples/dashboard/snapshots/apple-financial.public.json"
    before = source.read_bytes()
    published = json.loads(before)
    schema = DashboardSchemaV1.model_validate(copy.deepcopy(published["schema"]))
    widget = next(item for item in schema.widgets if item.id == "profit-trend")
    result = WidgetQueryResult.model_validate(
        published["snapshot"]["widgets"][widget.id]
    )
    assert normalize_executed_chart(schema, widget, result)
    assert widget.type.value == "bar"
    assert source.read_bytes() == before
    assert (
        next(
            item for item in published["schema"]["widgets"] if item["id"] == widget.id
        )["type"]
        == "line"
    )
