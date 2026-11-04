"""Shared query export and pi promotion preserve actual artifact payloads."""

import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbgpt_app.agent_harness.pi import tool_bridge
from dbgpt_app.openapi.api_v1.harness_pi_stream import _embedded_artifact_outputs
from dbgpt_app.openapi.api_v1.tools.export_csv import make_export_csv


def test_csv_exports_captured_rows_and_pi_promotes_file():
    state = {
        "_query_artifacts": {
            "sql-test": {
                "columns": ["Store", "销售额", "备注"],
                "rows": [[20, 301397792.46, '含逗号,和"引号"'], [4, None, ""]],
                "truncated": False,
            }
        }
    }
    result = json.loads(make_export_csv(state)("sql-test", "../top5.csv"))
    assert result["success"] is True
    file = result["chunks"][0]["content"]
    path = Path(file["file_path"])
    try:
        assert path.name == "top5.csv"
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
        assert rows == [
            ["Store", "销售额", "备注"],
            ["20", "301397792.46", '含逗号,和"引号"'],
            ["4", "", ""],
        ]
        assert _embedded_artifact_outputs(json.dumps(result)) == result["chunks"]
    finally:
        path.unlink()
        path.parent.rmdir()


def test_export_rejects_missing_or_truncated_artifact():
    export = make_export_csv({"_query_artifacts": {"partial": {"truncated": True}}})
    assert json.loads(export("missing"))["success"] is False
    assert json.loads(export("partial"))["success"] is False


def test_pi_preserves_native_chart_markdown():
    chart = {"output_type": "markdown", "content": "```vis-chart\n{}\n```"}
    assert _embedded_artifact_outputs(json.dumps({"chunks": [chart]})) == [chart]


@pytest.mark.asyncio
async def test_pi_suite_registers_and_executes_shared_artifact_tools(monkeypatch):
    from dbgpt_app.openapi.api_v1 import suite_binder
    from dbgpt_app.openapi.api_v1.subagent import react_tools
    from dbgpt_app.openapi.api_v1.tools import semantic_tools
    from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query
    from dbgpt_serve.datasource.manages import ConnectorManager

    connector = SimpleNamespace(run=lambda sql: [["Store", "total_sales"], [20, 10]])
    monkeypatch.setattr(
        ConnectorManager,
        "get_instance",
        lambda app: SimpleNamespace(get_connector=lambda name: connector),
    )
    monkeypatch.setattr(
        react_tools,
        "make_react_tools",
        lambda state, **kwargs: {"sql_query": make_sql_query(state, connector)},
    )
    monkeypatch.setattr(semantic_tools, "make_semantic_tools", lambda name: [])
    monkeypatch.setattr(tool_bridge, "_skill_tools", lambda *args: [])
    app = SimpleNamespace(
        get_component=lambda *args: SimpleNamespace(create=lambda: None)
    )
    conv_id = "pi-suite-artifact-test"
    suite_binder.set_conv_suite(
        conv_id,
        suite_binder.SuiteBinding(
            name="db-analysis",
            version="test",
            allow={"sql_query", "export_csv", "chart_query", "generate_report"},
            deny={"bash"},
        ),
    )
    path = None
    try:
        manifest = tool_bridge.register_conv_tools(
            conv_id, {"database_name": "test"}, app
        )
        assert {"export_csv", "chart_query", "generate_report"} <= {
            entry["name"] for entry in manifest
        }
        result = json.loads(
            await tool_bridge.run_tool(conv_id, "sql_query", {"sql": "SELECT 1"})
        )
        artifact_id = result["artifact_id"]
        assert artifact_id.startswith("sql-")
        export = json.loads(
            await tool_bridge.run_tool(
                conv_id, "export_csv", {"artifact_id": artifact_id}
            )
        )
        path = Path(export["chunks"][0]["content"]["file_path"])
        assert path.resolve().is_relative_to(Path("/tmp").resolve())
        assert "20,10" in path.read_text(encoding="utf-8-sig")
        assert (
            tool_bridge._REGISTRY[conv_id]["react_state"][
                "_report_artifact_sink"
            ].artifact_count
            == 1
        )
    finally:
        suite_binder.clear_conv_suite(conv_id)
        tool_bridge._REGISTRY.pop(conv_id, None)
        if path:
            path.unlink()
            path.parent.rmdir()


@pytest.mark.parametrize(
    "prompt,expected,excluded",
    [
        (
            "创建销售看板",
            {"plan_dashboard", "sql_query"},
            {"create_dashboard_draft", "repair_dashboard_draft", "bash"},
        ),
        (
            "[[confirm-dashboard:dash-1]] expected revision 1",
            {"create_dashboard_draft", "repair_dashboard_draft"},
            {"sql_query", "plan_dashboard", "bash"},
        ),
    ],
)
def test_pi_dashboard_tools_follow_native_phase_contract(
    monkeypatch, prompt, expected, excluded
):
    from dbgpt_app.openapi.api_v1 import suite_binder
    from dbgpt_app.openapi.api_v1.subagent import react_tools
    from dbgpt_app.openapi.api_v1.tools import semantic_tools
    from dbgpt_serve.datasource.manages import ConnectorManager

    connector = SimpleNamespace(db_type="sqlite")
    monkeypatch.setattr(
        ConnectorManager,
        "get_instance",
        lambda app: SimpleNamespace(get_connector=lambda name: connector),
    )
    monkeypatch.setattr(react_tools, "make_react_tools", lambda *args, **kwargs: {})
    monkeypatch.setattr(semantic_tools, "make_semantic_tools", lambda name: [])
    monkeypatch.setattr(tool_bridge, "_skill_tools", lambda *args: [])
    conv_id = "pi-dashboard-phase-test"
    try:
        manifest = tool_bridge.register_conv_tools(
            conv_id,
            {"database_name": "test"},
            SimpleNamespace(),
            {"_report_original_request": prompt, "owner_id": "user"},
        )
        names = {item["name"] for item in manifest}
        assert expected <= names
        assert not names.intersection(excluded)
        state = tool_bridge.get_react_state(conv_id)
        assert state["dashboard_agent_mode"]
        assert "DashboardPlan" in state["_dashboard_tool_contracts"] or (
            "DashboardQueryDraftRequest" in state["_dashboard_tool_contracts"]
        )
    finally:
        suite_binder.clear_conv_suite(conv_id)
        tool_bridge._REGISTRY.pop(conv_id, None)


def test_pi_history_preserves_dashboard_plan_and_generation_failure():
    from dbgpt_app.openapi.api_v1.harness_pi_stream import _build_pi_history_payload

    reference = {
        "dashboard_id": "dashboard-1",
        "status": "awaiting_confirmation",
        "current_revision": 1,
        "confirmation_prompt": "[[confirm-dashboard:dashboard-1]] revision 1",
    }
    failure = {"type": "dashboard.generation.failed", "reason": "incomplete"}
    payload = json.loads(
        _build_pi_history_payload(
            "未完成",
            [],
            dashboard_state={
                "dashboard_refs": [reference],
                "dashboard_generation_failure": failure,
            },
        )
    )
    assert payload["dashboard_refs"] == [reference]
    assert payload["dashboard_generation_failure"] == failure
