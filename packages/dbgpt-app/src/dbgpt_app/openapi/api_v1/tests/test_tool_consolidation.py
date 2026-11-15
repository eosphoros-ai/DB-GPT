"""Verify schema activation and the authorization boundaries it must retain."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dbgpt.agent.expand.tool_calling_agent import _build_openai_tools
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt_app.openapi.api_v1.react_prompt import build_react_prompt_template
from dbgpt_app.openapi.api_v1.suite_binder import SuiteBinding, canonical_suite_tool
from dbgpt_app.openapi.api_v1.tools.connector_gate import make_connector_gate
from dbgpt_app.openapi.api_v1.tools.tool_catalog import make_tool_search


def test_negative_dashboard_constraint_keeps_analysis_tools():
    from dbgpt_app.openapi.api_v1.agentic_data_api import _is_dashboard_workflow_request

    assert not _is_dashboard_workflow_request(
        "查询门店销售排名并给出柱状图。不要生成HTML报告或看板。"
    )
    assert not _is_dashboard_workflow_request(
        "Analyze sales. Do not create a dashboard."
    )
    assert _is_dashboard_workflow_request("创建销售看板")


@pytest.mark.asyncio
async def test_discovery_changes_next_native_schema_without_widening_permissions():
    @tool(description="Read approved data")
    def approved_data():
        return "data"

    @tool(description="Read secret data")
    def secret_data():
        raise AssertionError("must never execute")

    pack = ToolPack([])
    emit = AsyncMock()
    search = make_tool_search(
        ToolPack([approved_data, secret_data]).sub_resources,
        lambda: pack,
        lambda name: name == "approved_data",
        emit,
    )
    pack.append(search._tool)
    assert [item["function"]["name"] for item in _build_openai_tools(pack)] == [
        "tool_search"
    ]
    result = json.loads(await search("data"))
    assert [item["name"] for item in result["tools"]] == ["approved_data"]
    assert [item["function"]["name"] for item in _build_openai_tools(pack)] == [
        "tool_search",
        "approved_data",
    ]
    assert json.loads(await search("secret_data"))["tools"] == []
    emit.assert_awaited_once()


def test_native_prompt_removes_duplicate_inventory_but_keeps_evidence():
    template = build_react_prompt_template(
        "Task\n## Available Tools Description\n1. **obsolete**: long schema\n"
        "## User Attachments\nfile-123\n",
        financial_enabled=False,
    )
    native = template.format(
        action_space="FULL_SCHEMA",
        action_space_names="terminate",
        native_function_calling=True,
    )
    assert "obsolete" not in native and "FULL_SCHEMA" not in native
    assert "file-123" in native
    text = template.format(
        action_space="FULL_SCHEMA",
        action_space_names="terminate",
        native_function_calling=False,
    )
    assert "FULL_SCHEMA" in text


def test_historical_script_denies_cover_consolidated_runner():
    denies = {canonical_suite_tool("execute_skill_script_file")}
    binding = SuiteBinding(name="financial-analysis", version="1", deny=denies)
    assert binding.violation("run_skill_script")
    assert canonical_suite_tool("execute_skill_script") == "run_skill_script"


@pytest.mark.asyncio
async def test_direct_connector_write_keeps_confirmation_and_cancels_on_rejection():
    registry = SimpleNamespace(
        register=lambda _: None, wait_for=AsyncMock(return_value=False)
    )
    interceptor = SimpleNamespace(
        should_confirm=lambda *_: True, _summarize_args=lambda _: "write"
    )
    manager = SimpleNamespace(
        get_confirmation_interceptor=lambda: interceptor,
        get_confirmation_registry=lambda: registry,
    )
    gate = make_connector_gate(manager, {"connector_write"})
    assert await gate("connector_write", {"value": 1}) is not None
    assert await gate("unselected_tool", {}) is None
    registry.wait_for.assert_awaited_once()


@pytest.mark.asyncio
async def test_unified_file_runner_retains_arguments_and_lineage(monkeypatch):
    from dbgpt_app.openapi.api_v1.tools import skill_tools

    runner = AsyncMock(return_value='{"artifact_id":"real-capture"}')
    monkeypatch.setattr(skill_tools, "make_execute_skill_script_file", lambda _: runner)
    run = skill_tools.make_run_skill_script({})
    result = await run("registered", "script.py", {"x": 1}, ["upstream"])
    assert json.loads(result)["artifact_id"] == "real-capture"
    runner.assert_awaited_once_with(
        "registered", "script.py", {"x": 1}, ["upstream"], None
    )
    with pytest.raises(ValueError, match="exactly one"):
        await run("registered", "script.py", script_name="inline")
    with pytest.raises(ValueError, match="either"):
        await run("registered", "script.py", args={}, argv=[])
