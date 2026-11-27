"""The shipped financial suite binds executable commands and scoped tools."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dbgpt.agent.resource.tool.exceptions import ToolExecutionException
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt_app.openapi.api_v1.suite_binder import (
    bind_command,
    build_sop_block,
    command_binding_event,
    load_binding,
    skill_request_text,
)
from dbgpt_app.openapi.api_v1.tools.skill_tools import mount_suite_skills
from dbgpt_app.openapi.api_v1.tools.stock_quotes import make_stock_quote_tool
from dbgpt_serve.plugins.loader import load_suite_dir

SUITE_ROOT = (
    Path(__file__).resolve().parents[5] / "assets" / "suites" / "financial-analysis"
)
FINANCIAL_TOOLS = {
    "load_skill",
    "query_stock_quotes",
    "prepare_financial_report",
    "prepare_financial_comparison",
    "resolve_financial_comparison",
    "get_financial_topic",
    "save_financial_topic",
    "review_financial_report",
    "publish_financial_report",
    "read_financial_report",
}


@pytest.fixture
def financial_suite():
    package = load_suite_dir(SUITE_ROOT)
    assert package is not None
    row = SimpleNamespace(
        name=package.name,
        version=package.version,
        status="enabled",
        package_path=str(SUITE_ROOT),
        manifest_snapshot=package.snapshot,
    )
    with patch(
        "dbgpt_app.openapi.api_v1.suite_binder._plugins_service",
        return_value=SimpleNamespace(registry=SimpleNamespace(get=lambda slug: row)),
    ):
        binding = load_binding(package.name)
    assert binding is not None
    return package, binding


def test_financial_suite_needs_documents_not_database(financial_suite):
    package, binding = financial_suite
    assert package.warnings == []
    assert package.snapshot["context_defaults"]["datasource"] == "optional"
    assert package.snapshot["context_defaults"]["harness_engine"] == "dbgpt"
    assert package.snapshot["scenario_id"] == "financial"
    assert not binding.semantic
    assert not binding.watermark
    assert binding.allow == FINANCIAL_TOOLS
    assert len(package.manifest["commands"]) == 3
    assert any(
        skill["name"] == "financial-workflow" and not skill["user_invocable"]
        for skill in package.manifest["skills"]
    )


@pytest.mark.parametrize(
    "requested,canonical,skill",
    [
        ("/读年报", "/读年报", "annual-report"),
        ("/annual-report", "/读年报", "annual-report"),
        ("/财报对比", "/财报对比", "compare-reports"),
        ("/compare-reports", "/财报对比", "compare-reports"),
    ],
)
def test_commands_load_their_workflow_and_preserve_scope(
    financial_suite, requested, canonical, skill
):
    _, binding = financial_suite
    bind_command(binding, requested)
    assert not binding.command_error
    assert binding.command == canonical
    assert binding.command_skill == skill
    assert {doc["path"] for doc in binding.loaded_documents} == {
        f"skills/{skill}/SKILL.md",
        "prompts/financial-playbook.md",
        "skills/financial-workflow/SKILL.md",
    }
    prompt = build_sop_block(binding)
    assert "workflow.status=published" in prompt
    assert "不能把未完成任务标为完成" in prompt
    assert command_binding_event(binding)["skill_loaded"] is True
    for tool in FINANCIAL_TOOLS | {"question", "todowrite", "terminate"}:
        assert binding.violation(tool) is None
    for tool in (
        "sql_query",
        "bash",
        "code",
        "execute_skill_script",
        "execute_skill_script_file",
        "generate_report",
        "html_interpreter",
    ):
        assert binding.violation(tool)


def test_command_inputs_and_translations_are_projected(financial_suite):
    package, _ = financial_suite
    commands = {command["name"]: command for command in package.snapshot["commands"]}
    quote = commands["/查股票"]
    assert not quote.get("input_files")
    question = next(
        q
        for q in package.snapshot["recommended_questions"]
        if q["command"] == "/查股票"
    )
    assert (
        quote["prefill"] == question["text"] == "帮我查查今天科技股和贵州茅台涨了多少？"
    )
    assert quote["prefill_en"] == question["text_en"]
    assert "行业" in question["hint"]
    assert "sector" in question["hint_en"]
    _, binding = financial_suite
    bind_command(binding, "/stock-quote")
    assert binding.command == "/查股票" and not binding.command_error
    assert command_binding_event(binding)["skill_loaded"] is False
    assert not binding.loaded_documents
    assert "workflow.status=published" not in build_sop_block(binding)
    assert commands["/读年报"]["input_files"] == {
        "min": 1,
        "max": 1,
        "types": ["application/pdf"],
    }
    assert commands["/财报对比"]["input_files"] == {
        "min": 2,
        "max": 5,
        "types": ["application/pdf"],
    }
    assert commands["/读年报"]["display_en"] == "/annual-report"
    assert commands["/财报对比"]["display_en"] == "/compare-reports"
    assert all(
        command["prefill"] and command["prefill_en"] for command in commands.values()
    )


def test_quote_shortcut_only_offers_the_skill_until_the_agent_loads_it(financial_suite):
    _, binding = financial_suite
    state = {"financial_user_query": "/查股票 时间会证明光模块吗？"}
    bind_command(binding, "/查股票")
    assert (
        skill_request_text(state["financial_user_query"], binding)
        == "时间会证明光模块吗？"
    )
    assert (
        skill_request_text("/stock-quote 先查光模块，再解释长期需求。", binding)
        == "先查光模块，再解释长期需求。"
    )
    assert skill_request_text("解释 /查股票 怎么用", binding) == "解释 /查股票 怎么用"
    pack = ToolPack([])
    resources = {"query_stock_quotes": make_stock_quote_tool(state)}
    summary = mount_suite_skills(pack, binding, resources, state)
    assert "stock-quote" in summary
    assert [r.name for r in pack.sub_resources] == ["load_skill"]
    assert "query_stock_quotes" not in build_sop_block(binding)
    with pytest.raises(ToolExecutionException, match="unavailable"):
        pack.execute(resource_name="load_skill", skill_name="unrelated")
    result = pack.execute(resource_name="load_skill", skill_name="stock-quote")
    assert "query_stock_quotes" in result
    assert {r.name for r in pack.sub_resources} == {"load_skill", "query_stock_quotes"}
    assert "stock_quote_snapshot" not in state
    assert not binding.command_skill_text


def test_quote_shortcut_eager_mount_activates_tool_on_round_one(financial_suite):
    _, binding = financial_suite
    state = {"financial_user_query": "今天茅台涨了多少？"}
    bind_command(binding, "/查股票")
    pack = ToolPack([])
    resources = {"query_stock_quotes": make_stock_quote_tool(state)}
    summary = mount_suite_skills(
        pack, binding, resources, state, eager_skills=("stock-quote",)
    )
    assert "Preloaded skill: stock-quote" in summary
    assert {r.name for r in pack.sub_resources} == {"load_skill", "query_stock_quotes"}


@pytest.mark.parametrize("blocked", ["load_skill", "query_stock_quotes"])
def test_suite_tool_deny_applies_before_skill_activation(financial_suite, blocked):
    _, binding = financial_suite
    binding.deny.add(blocked)
    pack = ToolPack([])
    assert not mount_suite_skills(pack, binding, {"query_stock_quotes": None}, {})
    assert not pack.sub_resources


def test_unpinned_discovery_uses_enabled_registry_metadata_only(financial_suite):
    package, _ = financial_suite
    row = SimpleNamespace(
        name=package.name,
        version=package.version,
        status="enabled",
        package_path=package.path,
        manifest_snapshot=package.snapshot,
    )
    service = SimpleNamespace(registry=SimpleNamespace(get=lambda _: row))
    with patch(
        "dbgpt_app.openapi.api_v1.suite_binder._plugins_service", return_value=service
    ):
        with patch.object(
            Path, "read_text", side_effect=AssertionError("premature skill read")
        ):
            binding = load_binding(package.name, catalog_only=True)
            assert binding and binding.skills == [
                {"name": "stock-quote", "path": "skills/stock-quote/SKILL.md"}
            ]
            assert not binding.loaded_documents
            row.status = "disabled"
            assert load_binding(package.name, catalog_only=True) is None


def test_bound_shortcut_reads_skill_only_after_load(financial_suite, monkeypatch):
    package, _ = financial_suite
    row = SimpleNamespace(
        name=package.name,
        version=package.version,
        status="enabled",
        package_path=package.path,
        manifest_snapshot={**package.snapshot, "context_defaults": {}},
    )
    read_files = []
    read_text = Path.read_text

    def record_read(path, *args, **kwargs):
        read_files.append(path.relative_to(SUITE_ROOT).as_posix())
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record_read)
    with patch(
        "dbgpt_app.openapi.api_v1.suite_binder._plugins_service",
        return_value=SimpleNamespace(registry=SimpleNamespace(get=lambda _: row)),
    ):
        binding = load_binding(package.name)
    bind_command(binding, "/查股票")
    assert binding.context_defaults["harness_engine"] == "dbgpt"
    assert read_files == [".dbgpt-plugin/plugin.json", "prompts/financial-playbook.md"]
    pack = ToolPack([])
    mount_suite_skills(
        pack, binding, {"query_stock_quotes": make_stock_quote_tool({})}, {}
    )
    pack.execute(resource_name="load_skill", skill_name="stock-quote")
    assert read_files[2:] == ["skills/stock-quote/SKILL.md"]
