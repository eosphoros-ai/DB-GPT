"""Explicit suite commands carry intent without weakening file authorization."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    apply_financial_suite_context,
    financial_command_input_error,
    financial_completion_error,
    has_comparison_intent,
    is_financial_turn,
    make_financial_tools,
)


@pytest.mark.parametrize("command", ["/读年报", "/财报对比"])
def test_current_resolved_command_supplies_financial_context(command):
    binding = SimpleNamespace(
        name="financial-analysis",
        command=command,
        command_error="",
        command_skill_text="Loaded instructions",
    )
    state = {"financial_suite_command": "/stale-command"}
    apply_financial_suite_context(state, binding)
    assert state["financial_suite_command"] == command


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "another-suite"},
        {"command": "/unknown"},
        {"command": "/compare-reports"},
        {"command": ["/财报对比"]},
        {"command_error": "Skill could not be loaded"},
        {"command_skill_text": ""},
        {"command_skill_text": "   "},
        {"command_skill_text": None},
    ],
)
def test_invalid_bindings_clear_stale_financial_intent(changes):
    binding = SimpleNamespace(
        **{
            "name": "financial-analysis",
            "command": "/财报对比",
            "command_error": "",
            "command_skill_text": "Loaded instructions",
            **changes,
        }
    )
    state = {"financial_suite_command": "/财报对比"}
    apply_financial_suite_context(state, binding)
    assert "financial_suite_command" not in state


@pytest.mark.parametrize(
    "unresolved",
    [None, {"name": "financial-analysis", "suite_command": "/财报对比"}],
)
def test_request_metadata_cannot_supply_the_internal_financial_command(unresolved):
    state = {
        "financial_suite_command": "/财报对比",
        "suite": "financial-analysis",
        "suite_command": "/财报对比",
    }
    apply_financial_suite_context(state, unresolved)
    assert "financial_suite_command" not in state


@pytest.mark.parametrize("command", ["/读年报", "/财报对比"])
def test_resolved_financial_command_scopes_a_short_request(command):
    assert is_financial_turn(
        {"financial_suite_command": command, "financial_user_query": "请看附件"}
    )


@pytest.mark.parametrize("command", [None, "/analyze", "/unknown"])
def test_unresolved_or_other_commands_do_not_create_financial_intent(command):
    assert not is_financial_turn(
        {"financial_suite_command": command, "financial_user_query": "请看附件"}
    )
    assert not has_comparison_intent("请看附件", command=command)


def test_comparison_selection_supplies_intent_but_single_report_does_not():
    assert has_comparison_intent("这两份", command="/财报对比")
    assert not has_comparison_intent("这两份", command="/读年报")


@pytest.mark.parametrize(
    "query",
    [
        "不要比较，只读第一份",
        "不需要进行对比",
        "Don't compare these reports",
        "不要比较，只解释横向这个词",
    ],
)
@pytest.mark.asyncio
async def test_explicit_negative_request_overrides_the_selected_comparison(query):
    assert not has_comparison_intent(query, command="/财报对比")
    state = {
        "financial_suite_command": "/财报对比",
        "financial_user_query": query,
    }
    service = SimpleNamespace(comparisons=SimpleNamespace(create=Mock()))
    tool = next(
        tool
        for tool in make_financial_tools(state, service=service)
        if tool.__name__ == "prepare_financial_comparison"
    )
    with pytest.raises(ValueError, match="未明确要求"):
        await tool(file_ids=["one", "two"], comparison_kind="peer")
    service.comparisons.create.assert_not_called()


@pytest.mark.asyncio
async def test_selected_comparison_still_requires_current_session_files():
    state = {
        "owner_id": "alice",
        "conv_id": "current",
        "financial_suite_command": "/财报对比",
        "financial_user_query": "这两份",
        "session_files": [SimpleNamespace(file_id="one", name="one.pdf")],
    }
    service = SimpleNamespace(comparisons=SimpleNamespace(create=Mock()))
    tool = next(
        tool
        for tool in make_financial_tools(state, service=service)
        if tool.__name__ == "prepare_financial_comparison"
    )
    with pytest.raises(ValueError, match="当前对话已授权"):
        await tool(file_ids=["one", "another-session"], comparison_kind="peer")
    service.comparisons.create.assert_not_called()


@pytest.mark.asyncio
async def test_financial_command_uses_saved_report_despite_a_stale_database_selection():
    state = {
        "owner_id": "alice",
        "conv_id": "current",
        "financial_suite_command": "/读年报",
        "financial_user_query": "请再解释一下",
        "financial_other_source_selected": True,
    }
    service = SimpleNamespace(latest_agent_report=Mock(return_value={"revision": "v1"}))
    result = await financial_completion_error(state, service=service)
    assert "read_financial_report" in result
    service.latest_agent_report.assert_called_once_with("alice", "current")


@pytest.mark.parametrize("command", [None, "/财报对比"])
@pytest.mark.parametrize(
    "query",
    [
        "比较 A 和 B，不要比较 C",
        "不要比较 C；请比较 A 和 B",
        "不要比较 C 但比较 A 和 B",
        "Compare A and B, don't compare C",
        "Do not compare C but compare A and B",
    ],
)
def test_an_excluded_report_does_not_cancel_a_separate_comparison(query, command):
    assert has_comparison_intent(query, command=command)


@pytest.mark.parametrize("command", ["/读年报", "/财报对比"])
def test_new_analysis_commands_cannot_use_saved_reports_instead_of_attachments(command):
    error = financial_command_input_error(command, has_files=False)
    assert "上传" in error
    assert "追问已有报告" in error
    assert financial_command_input_error(command, has_files=True) is None
    assert "Upload" in financial_command_input_error(
        command, has_files=False, language="en"
    )


def test_ordinary_report_followups_do_not_require_new_attachments():
    assert financial_command_input_error(None, has_files=False) is None
