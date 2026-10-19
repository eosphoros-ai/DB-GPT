from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardSchemaV1
from dbgpt_app.openapi.api_v1.dashboard.target_resolution import (
    resolve_dashboard_target,
)


def _schema(*, tied_right: bool = False) -> DashboardSchemaV1:
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.0",
            "dashboard": {
                "id": "dashboard-1",
                "title": "经营看板",
                "data_source_id": "demo",
            },
            "widgets": [
                {
                    "id": "revenue",
                    "type": "kpi",
                    "title": "营业收入",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT 1 AS value",
                        "output_fields": [{"name": "value", "type": "number"}],
                    },
                    "encoding": {"value": "value"},
                },
                {
                    "id": "revenue-trend",
                    "type": "line",
                    "title": "营业收入趋势",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT 1 AS month, 2 AS value",
                        "output_fields": [
                            {"name": "month", "type": "string"},
                            {"name": "value", "type": "number"},
                        ],
                    },
                    "encoding": {"x": "month", "y": "value"},
                },
            ],
            "layouts": {
                "desktop": [
                    {"widget_id": "revenue", "x": 0, "y": 0, "w": 6, "h": 4},
                    {
                        "widget_id": "revenue-trend",
                        "x": 6 if not tied_right else 0,
                        "y": 0,
                        "w": 6,
                        "h": 4,
                    },
                ]
            },
        }
    )


def test_explicit_longest_title_resolves_without_short_title_collision():
    result = resolve_dashboard_target(_schema(), "把营业收入趋势改成柱状图")

    assert result.status.value == "resolved"
    assert result.target is not None
    assert result.target.widget_id == "revenue-trend"
    assert result.matched_by == "title"


def test_right_side_reference_uses_desktop_layout():
    result = resolve_dashboard_target(_schema(), "右边那个改一下")

    assert result.status.value == "resolved"
    assert result.target is not None
    assert result.target.widget_id == "revenue-trend"
    assert result.matched_by == "position_right"


def test_tied_spatial_reference_requires_clarification():
    result = resolve_dashboard_target(_schema(tied_right=True), "右边那个改一下")

    assert result.status.value == "needs_clarification"
    assert result.target is None
    assert {item.widget_id for item in result.candidates} == {
        "revenue",
        "revenue-trend",
    }
    assert result.question


def test_deictic_reference_uses_only_explicit_current_selection():
    result = resolve_dashboard_target(
        _schema(), "这个图太挤了", selected_widget_id="revenue"
    )

    assert result.status.value == "resolved"
    assert result.target is not None
    assert result.target.widget_id == "revenue"
    assert result.matched_by == "current_selection"


def test_deictic_reference_without_selection_never_guesses():
    result = resolve_dashboard_target(_schema(), "这个图太挤了")

    assert result.status.value == "needs_clarification"
    assert result.target is None
    assert len(result.candidates) == 2
    assert result.matched_by == "missing_selection"


def test_unknown_reference_with_multiple_widgets_never_guesses():
    result = resolve_dashboard_target(_schema(), "帮我改得更清楚")

    assert result.status.value == "needs_clarification"
    assert result.target is None
    assert len(result.candidates) == 2


def test_one_widget_dashboard_can_resolve_implicit_reference():
    schema = _schema()
    schema.widgets = schema.widgets[:1]
    schema.layouts.desktop = schema.layouts.desktop[:1]

    result = resolve_dashboard_target(schema, "改得更清楚")

    assert result.status.value == "resolved"
    assert result.target is not None
    assert result.target.widget_id == "revenue"
    assert result.matched_by == "single_widget"
