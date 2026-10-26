import threading
import time
from datetime import datetime

from dbgpt_app.openapi.api_v1.dashboard.query_executor import DashboardQueryExecutor
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardSchemaV1,
    WidgetQueryResult,
)


def _schema(widget_count: int = 4) -> DashboardSchemaV1:
    widgets = []
    layouts = []
    for index in range(widget_count):
        widget_id = f"metric-{index}"
        widgets.append(
            {
                "id": widget_id,
                "type": "kpi",
                "title": widget_id,
                "query": {
                    "data_source_id": "fixture",
                    "sql": "SELECT 1 AS value",
                    "output_fields": [{"name": "value", "type": "number"}],
                },
                "encoding": {"value": "value"},
            }
        )
        layouts.append({"widget_id": widget_id, "x": 0, "y": index * 2, "w": 4, "h": 2})
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.2",
            "dashboard": {"title": "Limits", "data_source_id": "fixture"},
            "widgets": widgets,
            "layouts": {"desktop": layouts},
        }
    )


def test_dashboard_refresh_concurrency_is_bounded():
    executor = DashboardQueryExecutor(max_dashboard_workers=2)
    lock = threading.Lock()
    active = 0
    max_active = 0

    def execute_widget(_schema, widget_id, _filters):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return WidgetQueryResult(widget_id=widget_id, refreshed_at=datetime.now())

    executor.execute_widget = execute_widget
    results = executor.execute_dashboard(_schema(), {})

    assert set(results) == {f"metric-{index}" for index in range(4)}
    assert max_active == 2


def test_dashboard_refresh_deadline_isolated_to_unfinished_widgets():
    executor = DashboardQueryExecutor(max_dashboard_workers=2)
    executor.max_dashboard_seconds = 0.01

    def execute_widget(_schema, widget_id, _filters):
        time.sleep(0.05)
        return WidgetQueryResult(widget_id=widget_id, refreshed_at=datetime.now())

    executor.execute_widget = execute_widget
    results = executor.execute_dashboard(_schema(2), {})

    assert {result.error.code for result in results.values()} == {
        "dashboard_refresh_timeout"
    }
    time.sleep(0.06)  # Let the bounded background work finish before teardown.
