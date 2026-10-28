"""Verify semantic tool calls and native suite gates without an LLM."""

import asyncio
import json
from pathlib import Path

from dbgpt_app.openapi.api_v1.suite_binder import (
    SuiteBinding,
    canonical_suite_tool,
)
from dbgpt_app.openapi.api_v1.tools.semantic_tools import make_semantic_tools


class Reader:
    def get_metric(self, **kwargs):
        return {"status": "ok", "metric": kwargs}


def test_tool_factory_binds_database_and_preserves_version_arguments():
    assert make_semantic_tools(None) == []
    tools = make_semantic_tools("orders_db", reader=Reader())
    names = [t._tool.name for t in tools]
    assert names == [
        "semantic_get_metadata",
        "semantic_search_business",
        "semantic_search_metrics",
        "semantic_get_metric",
    ]
    loop = asyncio.new_event_loop()
    try:
        result = json.loads(loop.run_until_complete(tools[3](metric_id=7, version=2)))
    finally:
        loop.close()
    assert result["metric"] == {"metric_id": 7, "metric_name": "", "version": 2}
    assert "database_name" not in tools[3]._tool.args
    assert "ds_id" not in tools[3]._tool.args


def test_native_query_and_analysis_suites_allow_all_semantic_reads():
    root = Path(__file__).resolve().parents[5] / "assets" / "suites"
    for slug in ("db-query", "db-analysis"):
        manifest = json.loads(
            (root / slug / ".qwenwork-plugin" / "plugin.json").read_text()
        )
        binding = SuiteBinding(
            name=slug,
            version=manifest["version"],
            allow={
                canonical_suite_tool(n) for n in manifest["dbgpt"]["tools"]["allow"]
            },
        )
        for t in make_semantic_tools("orders_db"):
            assert binding.violation(t._tool.name) is None
        assert binding.violation("bash") is not None


def test_pi_manifest_includes_semantic_tools_only_for_loaded_database(monkeypatch):
    from dbgpt_app.agent_harness.pi import tool_bridge
    from dbgpt_app.openapi.api_v1.subagent import react_tools
    from dbgpt_serve.datasource.manages import ConnectorManager

    class Manager:
        def get_connector(self, name):
            assert name == "orders_db"
            return object()

    monkeypatch.setattr(ConnectorManager, "get_instance", lambda app: Manager())
    monkeypatch.setattr(react_tools, "make_react_tools", lambda *a, **kw: {})
    monkeypatch.setattr(tool_bridge, "_skill_tools", lambda *a, **kw: [])
    try:
        manifest = tool_bridge.register_conv_tools(
            "semantic-test", {"database_name": "orders_db"}, object()
        )
        semantic = [t for t in manifest if t["name"].startswith("semantic_")]
        assert len(semantic) == 4
        for t in semantic:
            assert "database_name" not in t["parameters"]["properties"]
            assert "ds_id" not in t["parameters"]["properties"]
        manifest = tool_bridge.register_conv_tools("semantic-test", {}, object())
        assert not any(t["name"].startswith("semantic_") for t in manifest)
    finally:
        tool_bridge._REGISTRY.pop("semantic-test", None)
