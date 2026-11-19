"""The shipped financial suite binds executable commands and scoped tools."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dbgpt_app.openapi.api_v1.suite_binder import (
    bind_command,
    build_sop_block,
    command_binding_event,
    load_binding,
)
from dbgpt_serve.plugins.loader import load_suite_dir

SUITE_ROOT = (
    Path(__file__).resolve().parents[5] / "assets" / "suites" / "financial-analysis"
)
FINANCIAL_TOOLS = {
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
        return_value=SimpleNamespace(get=lambda slug: row),
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
    assert len(package.manifest["commands"]) == 2
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
