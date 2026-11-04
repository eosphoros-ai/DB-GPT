"""Integration tests for ToolCallingReActAgent action dispatch.

These drive the agent's ``act()`` through the real ``ConversableAgent.act``
dispatch loop (the same loop ``generate_reply`` — and thus the
``/api/v1/chat/react-agent`` endpoint — uses) but with a stubbed resource, so
no LLM/network is required.
"""

import json
from types import SimpleNamespace

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.expand.actions.tool_action import ToolCallSpec, run_tools_batch
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["output", "result", "final_answer"])
async def test_text_terminate_returns_only_final_answer(key):
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    out = await agent.act(
        AgentMessage(
            content=(
                "Thought: Task finished.\nAction: terminate\n"
                f'Action Input: {{"{key}": "技能已创建"}}'
            )
        ),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success is True
    assert out.terminate is True
    assert out.content == "技能已创建"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["...", "…", "", "  "])
async def test_placeholder_terminate_does_not_end_task(answer):
    out = await Terminate().run(
        "Thought: Retry with shell.\nAction: terminate\nAction Input: "
        + json.dumps({"output": answer})
    )
    assert out.is_exe_success is False
    assert out.terminate is False
    with pytest.raises(ValueError, match="non-empty final answer"):
        Terminate().execute(output=answer)
    native = await run_tools_batch(
        [ToolCallSpec(name="terminate", args={"output": answer})],
        ToolPack([Terminate()]),
        need_vis_render=False,
    )
    assert native.is_exe_success is False
    assert native.terminate is not True


@tool(description="Add two numbers")
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool(description="Multiply two numbers")
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


MULTI_STEP = (
    "Thought: compute both results.\n"
    "Action: add\n"
    'Action Input: {"a": 1, "b": 2}\n'
    "Thought: also multiply.\n"
    "Action: multiply\n"
    'Action Input: {"a": 3, "b": 4}\n'
)


def _make_agent(enable_parallel: bool) -> ToolCallingReActAgent:
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="test",
        enable_parallel_tool_execution=enable_parallel,
    )
    pack = ToolPack([add._tool, multiply._tool])
    agent.resource = pack
    for action in agent.actions:
        action.init_resource(pack)
    return agent


def _act_kwargs(agent, enable_parallel):
    """Simulate the kwargs generate_reply passes to act() via prepare_act_param."""
    return {
        "parser": agent.parser,
        "enable_parallel": enable_parallel,
        "tool_calls": None,
    }


@pytest.mark.asyncio
async def test_native_public_progress_arrives_before_tool_execution(monkeypatch):
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    calls = [
        {
            "id": "call-1",
            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
        },
    ]
    events = []

    async def select_model(self, last_model):
        return "test-model"

    async def create_with_output(**kwargs):
        assert (
            "without Thought, Action, Action Input" in kwargs["messages"][0]["content"]
        )
        assert all(
            "thought" not in item["function"]["parameters"]["properties"]
            for item in kwargs["tools"]
        )
        await kwargs["stream_callback"](
            {"delta_text": "先计算", "delta_thinking": "private"}
        )
        return SimpleNamespace(
            text="先计算总数，再核对结果。",
            has_text=True,
            tool_calls=calls,
        )

    async def callback(payload):
        events.append(payload)

    monkeypatch.setattr(ToolCallingReActAgent, "_a_select_llm_model", select_model)
    object.__setattr__(
        agent, "llm_client", SimpleNamespace(create_with_output=create_with_output)
    )
    text, _ = await agent._thinking_native(
        [], prompt="Compute 1 + 2", stream_callback=callback
    )
    assert events == [
        {
            "delta_text": "先计算",
            "delta_thinking": "private",
            "public_text_stream": True,
        },
        {"action_start": True, "public_text": text, "tool_calls": calls},
    ]
    assert text == "先计算总数，再核对结果。"
    kwargs = _act_kwargs(agent, False)
    kwargs["tool_calls"] = calls
    out = await agent.act(AgentMessage(content=text), sender=agent, **kwargs)
    assert out.is_exe_success is True
    assert out.action == "add"
    assert json.loads(out.action_input) == {"a": 1, "b": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["html_interpreter", "append_report_sections"])
async def test_invalid_report_call_uses_bounded_repair_handler(name):
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    failures = []

    def handle(raw_call, reason):
        failures.append((raw_call, reason))
        return "Report call needs valid JSON"

    object.__setattr__(
        agent,
        "_report_repair_state",
        {
            "_report_invalid_call_handler": handle,
        },
    )
    calls = [{"function": {"name": name, "arguments": '{"sections":['}}]
    object.__setattr__(agent, "_pending_native_tool_calls", calls)
    kwargs = _act_kwargs(agent, False)
    kwargs["tool_calls"] = calls
    out = await agent.act(AgentMessage(content=""), sender=agent, **kwargs)
    assert out.is_exe_success is False
    assert len(failures) == 1
    assert "JSON line" in failures[0][1]
    assert out.content == "Report call needs valid JSON"


@pytest.mark.asyncio
async def test_act_parallel_executes_multiple_steps():
    agent = _make_agent(enable_parallel=True)
    out = await agent.act(
        AgentMessage(content=MULTI_STEP),
        sender=agent,
        **_act_kwargs(agent, True),
    )
    assert out.is_exe_success is True
    # Both tools ran in one turn and were aggregated.
    assert out.action == "add, multiply"
    results = json.loads(out.observations)
    assert [r["name"] for r in results] == ["add", "multiply"]


@pytest.mark.asyncio
async def test_act_parallel_disabled_preserves_single_step_behaviour():
    agent = _make_agent(enable_parallel=False)
    out = await agent.act(
        AgentMessage(content=MULTI_STEP),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    # Legacy behaviour: only the first action runs (single action per round).
    assert out.is_exe_success is True
    assert out.action == "add"
    assert out.observations == "3"
