"""Regression tests for the lead-agent parallel-dispatch instructions."""

import re
from pathlib import Path

from dbgpt_app.openapi.api_v1.subagent.dispatcher import (
    DISPATCH_PROMPT_SECTION,
    make_dispatch_tool,
)
from dbgpt_app.openapi.api_v1.tools.todowrite import make_todowrite


def test_dispatch_prompt_recognizes_two_independent_readonly_tasks():
    prompt = DISPATCH_PROMPT_SECTION
    normalized_prompt = " ".join(prompt.split())

    assert "at least 2 clearly scoped subtasks" in normalized_prompt
    assert '"separately", "respectively"' in normalized_prompt
    assert "against the same database or table" in normalized_prompt
    assert "multiple independent read-only queries or analyses" in normalized_prompt
    assert "share intermediate results" in normalized_prompt
    assert "Never skip `todowrite`" in normalized_prompt
    assert "mark those items as `completed`" in normalized_prompt
    assert "exactly one todo item marked as `in_progress`" in normalized_prompt
    assert "B requires A's result" in normalized_prompt
    assert "[Good candidates for parallel dispatch]" in normalized_prompt
    assert "[Do not use parallel dispatch]" in normalized_prompt
    assert not re.search(r"[\u4e00-\u9fff]", prompt)


def test_dispatch_tool_description_matches_same_source_policy():
    async def emit_event(_payload):
        return None

    tool = make_dispatch_tool(
        parent_conv_id="prompt-test",
        llm_client=object(),
        emit_event=emit_event,
    )
    description = tool._tool.description

    assert "至少 2 个" in description
    assert "同一数据库或同一张表上的独立只读分析也可以并行" in description
    assert "只有共享中间结果、计算状态或存在前后依赖时才应串行" in description
    assert "对同一份数据的多角度切片，请直接" not in description


def test_full_agent_prompt_exposes_dispatch_and_two_task_todo_exception():
    api_v1_dir = Path(__file__).resolve().parents[2]
    source = (api_v1_dir / "agentic_data_api.py").read_text(encoding="utf-8")
    full_prompt = source.split(
        "# Full prompt with all tools when no skill is pre-selected", maxsplit=1
    )[1].split('""".strip()', maxsplit=1)[0]
    normalized_prompt = " ".join(full_prompt.split())

    assert "2 or more mutually independent subtasks" in normalized_prompt
    assert "even when the overall task has fewer than 3 steps" in normalized_prompt
    tools_section = full_prompt.split("## Available Tools Description", maxsplit=1)[
        1
    ].split("{file_context}", maxsplit=1)[0]
    assert tools_section.count("15. **dispatch_parallel_tasks**") == 1
    assert "16. **question**" in full_prompt
    assert "17. **terminate**" in full_prompt


def test_todowrite_tool_description_allows_two_parallel_candidates():
    todo_tool = make_todowrite([], lambda *_args: None)

    assert "2 or more mutually independent subtasks" in todo_tool._tool.description
