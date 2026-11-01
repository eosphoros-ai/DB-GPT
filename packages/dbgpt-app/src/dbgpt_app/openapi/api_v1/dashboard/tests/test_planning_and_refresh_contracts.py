from datetime import date

from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.query_executor import DashboardQueryExecutor
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardPlan,
    DashboardSchemaV1,
    collect_schema_issues,
)


def test_relative_date_is_recomputed_for_each_execution_day():
    schema = DashboardSchemaV1.model_validate(
        {
            "dashboard": {"title": "Rolling", "data_source_id": "sales"},
            "filters": [
                {
                    "id": "dates",
                    "type": "date_range",
                    "label": "Date",
                    "field": "sale_date",
                    "default": ["2020-01-01", "2020-01-31"],
                    "relative_date": {
                        "anchor": "today",
                        "start_offset_days": -6,
                        "end_offset_days": 0,
                    },
                }
            ],
        }
    )

    assert DashboardQueryExecutor.filter_values(
        schema, {}, today=date(2026, 8, 30)
    ) == {"dates": ["2026-08-24", "2026-08-30"]}
    assert DashboardQueryExecutor.filter_values(schema, {}, today=date(2026, 9, 2)) == {
        "dates": ["2026-08-27", "2026-09-02"]
    }
    assert DashboardQueryExecutor.filter_values(
        schema,
        {"dates": ["2026-01-01", "2026-01-07"]},
        today=date(2026, 9, 2),
    ) == {"dates": ["2026-01-01", "2026-01-07"]}


def test_relative_date_rejects_reversed_or_non_date_ranges():
    schema = DashboardSchemaV1.model_validate(
        {
            "dashboard": {"title": "Invalid", "data_source_id": "sales"},
            "filters": [
                {
                    "id": "region",
                    "type": "select",
                    "label": "Region",
                    "field": "region",
                    "relative_date": {
                        "start_offset_days": 2,
                        "end_offset_days": -2,
                    },
                }
            ],
        }
    )

    assert {issue.code for issue in collect_schema_issues(schema)} >= {
        "relative_date_requires_date_range",
        "relative_date_range_reversed",
    }


def test_relative_date_is_bound_by_backend_when_scheduler_sends_no_fixed_dates():
    class Connector:
        db_type = "sqlite"

        def __init__(self):
            self.params = None

        def get_table_names(self):
            return ["sales"]

        def get_fields(self, *_args):
            return [("sale_date", "date"), ("amount", "number")]

        def query_ex(self, _sql, params=None, timeout=None):
            self.params = params
            return ["amount"], [(42,)]

    schema = DashboardSchemaV1.model_validate(
        {
            "dashboard": {"title": "Scheduled", "data_source_id": "sales"},
            "filters": [
                {
                    "id": "dates",
                    "type": "date_range",
                    "label": "Date",
                    "field": "sale_date",
                    "relative_date": {
                        "start_offset_days": -6,
                        "end_offset_days": 0,
                    },
                }
            ],
            "widgets": [
                {
                    "id": "sales-total",
                    "type": "kpi",
                    "title": "Sales",
                    "query": {
                        "data_source_id": "sales",
                        "sql": (
                            "SELECT SUM(amount) AS amount FROM sales "
                            "WHERE sale_date BETWEEN :start_date AND :end_date"
                        ),
                        "filter_parameters": {
                            "dates": {
                                "start_parameter": "start_date",
                                "end_parameter": "end_date",
                            }
                        },
                        "output_fields": [{"name": "amount", "type": "number"}],
                    },
                    "encoding": {"value": "amount"},
                }
            ],
            "layouts": {
                "desktop": [
                    {"widget_id": "sales-total", "x": 0, "y": 0, "w": 4, "h": 3}
                ]
            },
        }
    )
    connector = Connector()
    result = DashboardQueryExecutor(
        connector_resolver=lambda _source_id: connector
    ).execute_widget(schema, "sales-total", {})
    today = date.today()

    assert result.error is None
    assert connector.params == {
        "start_date": date.fromordinal(today.toordinal() - 6).isoformat(),
        "end_date": today.isoformat(),
    }


def test_plan_orders_widgets_by_decision_level_and_persists_rationale():
    plan = DashboardPlan.model_validate(
        {
            "title": "Executive health",
            "business_theme": "Operating health",
            "audience": "Executive team",
            "decision_goal": "Decide where to intervene first",
            "analysis_logic": ["Assess status", "Locate drivers"],
            "layout_rationale": "Primary decisions precede diagnostics",
            "filter_strategy": "Rolling T-29 to T",
            "metrics": ["Sales"],
            "dimensions": ["Date"],
            "widgets": [
                {
                    "id": "trend",
                    "type": "line",
                    "title": "Sales trend",
                    "business_question": "How is sales changing?",
                    "metric": "Sales",
                    "dimensions": ["Date"],
                    "analysis_level": 3,
                    "rationale": "Explains the headline",
                    "layout": {"width": "half", "height": "tall"},
                },
                {
                    "id": "headline",
                    "type": "kpi",
                    "title": "Total sales",
                    "business_question": "Are sales healthy?",
                    "metric": "Sales",
                    "analysis_level": 1,
                    "rationale": "Primary decision signal",
                    "layout": {"width": "full", "height": "compact"},
                },
            ],
        }
    )

    planner = DashboardPlannerService(None)  # type: ignore[arg-type]
    schema = planner._build_schema(
        plan=plan,
        query_map={},
        data_source_id="sales",
        conversation_id="conversation-1",
        prompt="plan",
        model_name="test-model",
    )

    assert [widget.id for widget in schema.widgets] == ["headline", "trend"]
    assert [(item.widget_id, item.w, item.h) for item in schema.layouts.desktop] == [
        ("headline", 12, 3),
        ("trend", 6, 7),
    ]
    assert schema.schema_version == "1.4"
    assert schema.dashboard.theme.preset.value == "clarity"
    assert schema.dashboard.theme.mode.value == "light"
    stored_plan = schema.metadata.compatibility["dashboard_plan"]
    assert stored_plan["decision_goal"] == "Decide where to intervene first"
    assert stored_plan["widgets"][1]["rationale"] == "Primary decision signal"
