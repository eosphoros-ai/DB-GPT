"""Tests for parallel (batch) tool execution and ParallelToolAction."""

import json

import pytest

from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.expand.actions.tool_action import (
    ToolCallSpec,
    run_tool,
    run_tools_batch,
    split_joined_action,
)
from dbgpt.agent.expand.tool_calling_agent import (
    NativeToolCallAction,
    ParallelToolAction,
)
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack


@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool(description="Multiply two numbers")
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


@tool(description="Explode on purpose")
def explode() -> str:
    """Always fails."""
    raise RuntimeError("boom")


def _pack(*tools):
    return ToolPack([fn._tool for fn in tools])


@pytest.mark.asyncio
async def test_run_tools_batch_success():
    resource = _pack(add, multiply)
    out = await run_tools_batch(
        [
            ToolCallSpec(name="add", args={"a": 1, "b": 2}),
            ToolCallSpec(name="multiply", args={"a": 3, "b": 4}),
        ],
        resource,
        need_vis_render=False,
    )
    assert out.is_exe_success is True
    assert out.terminate is None
    assert out.action == "add, multiply"
    results = json.loads(out.observations)
    assert len(results) == 2
    assert [r["name"] for r in results] == ["add", "multiply"]
    assert "3" in out.content  # 1 + 2
    assert "12" in out.content  # 3 * 4


@pytest.mark.asyncio
async def test_run_tools_batch_single_forwards():
    resource = _pack(add, multiply)
    out = await run_tools_batch(
        [ToolCallSpec(name="add", args={"a": 2, "b": 5})],
        resource,
        need_vis_render=False,
    )
    assert out.is_exe_success is True
    # single-element batch uses the legacy run_tool path: observations is str
    assert out.observations == "7"


@pytest.mark.asyncio
async def test_run_tools_batch_partial_failure():
    resource = _pack(add, explode)
    out = await run_tools_batch(
        [
            ToolCallSpec(name="add", args={"a": 1, "b": 1}),
            ToolCallSpec(name="explode", args={}),
        ],
        resource,
        need_vis_render=False,
    )
    assert out.is_exe_success is False
    results = json.loads(out.observations)
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "explode" in out.content


@pytest.mark.asyncio
async def test_run_tools_batch_terminate_aggregation():
    resource = ToolPack([add._tool, Terminate()])
    out = await run_tools_batch(
        [
            ToolCallSpec(name="add", args={"a": 1, "b": 2}),
            ToolCallSpec(name="terminate", args={"output": "final answer"}),
        ],
        resource,
        need_vis_render=False,
    )
    assert out.terminate is True
    assert "final answer" in out.content


@pytest.mark.asyncio
async def test_run_tools_batch_empty():
    out = await run_tools_batch([], None, need_vis_render=False)
    assert out.is_exe_success is False


PARALLEL_TEXT = (
    "Thought: compute the sum.\n"
    "Action: add\n"
    'Action Input: {"a": 1, "b": 2}\n'
    "Thought: compute the product.\n"
    "Action: multiply\n"
    'Action Input: {"a": 3, "b": 4}\n'
)


@pytest.mark.asyncio
async def test_parallel_tool_action_multi_step():
    action = ParallelToolAction()
    action.init_resource(_pack(add, multiply))
    out = await action.run(PARALLEL_TEXT, enable_parallel=True, need_vis_render=False)
    assert out.is_exe_success is True
    assert out.action == "add, multiply"
    assert out.thoughts == "compute the sum.\ncompute the product."
    results = json.loads(out.observations)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_parallel_tool_action_single_step_delegates():
    single = 'Thought: add them.\nAction: add\nAction Input: {"a": 2, "b": 3}\n'
    action = ParallelToolAction()
    action.init_resource(_pack(add, multiply))
    out = await action.run(single, need_vis_render=False)
    assert out.is_exe_success is True
    assert out.action == "add"
    assert out.observations == "5"


@pytest.mark.asyncio
async def test_native_tool_call_action_batch():
    action = NativeToolCallAction()
    action.init_resource(_pack(add, multiply))
    tool_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
        },
        {
            "id": "c2",
            "type": "function",
            "function": {"name": "multiply", "arguments": '{"a": 3, "b": 4}'},
        },
    ]
    out = await action.run("", tool_calls=tool_calls, need_vis_render=False)
    assert out.is_exe_success is True
    assert out.action == "add, multiply"
    results = json.loads(out.observations)
    assert [r["name"] for r in results] == ["add", "multiply"]
    assert [r["call_id"] for r in results] == ["c1", "c2"]


@pytest.mark.asyncio
async def test_native_tool_call_action_falls_back_to_text():
    action = NativeToolCallAction()
    action.init_resource(_pack(add, multiply))
    out = await action.run(PARALLEL_TEXT, enable_parallel=True, need_vis_render=False)
    assert out.is_exe_success is True
    assert out.action == "add, multiply"


class TestSplitJoinedAction:
    """Text-ReAct turns can join actions: ``Action: a, b`` + array input."""

    def test_pairs_names_with_args(self):
        specs = split_joined_action(
            "sql_query, sql_query", [{"sql": "select 1"}, {"sql": "select 2"}]
        )
        assert specs is not None
        assert [s.name for s in specs] == ["sql_query", "sql_query"]
        assert specs[1].args == {"sql": "select 2"}

    def test_extra_args_use_last_name(self):
        specs = split_joined_action(
            "add, multiply", [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
        )
        assert specs is not None
        assert [s.name for s in specs] == ["add", "multiply", "multiply"]

    def test_non_dict_items_become_empty_args(self):
        specs = split_joined_action("add", ["oops"])
        assert specs is not None and specs[0].args == {}

    def test_non_list_args_untouched(self):
        assert split_joined_action("add", {"a": 1, "b": 2}) is None
        assert split_joined_action("add", []) is None
        assert split_joined_action("", [{"a": 1}]) is None


@pytest.mark.asyncio
async def test_run_tool_joined_action_executes_as_batch():
    """The crash case: joined name + list args must run as a real batch."""
    resource = _pack(add, multiply)
    out = await run_tool(
        "add, multiply",
        [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
        resource,
        need_vis_render=False,
    )
    assert out.is_exe_success is True
    assert out.action == "add, multiply"
    results = json.loads(out.observations)
    assert [r["name"] for r in results] == ["add", "multiply"]
    assert "3" in out.content and "12" in out.content
