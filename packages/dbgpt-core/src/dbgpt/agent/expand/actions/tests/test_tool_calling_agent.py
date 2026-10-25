"""Integration tests for ToolCallingReActAgent action dispatch.

These drive the agent's ``act()`` through the real ``ConversableAgent.act``
dispatch loop (the same loop ``generate_reply`` — and thus the
``/api/v1/chat/react-agent`` endpoint — uses) but with a stubbed resource, so
no LLM/network is required.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


@pytest.mark.asyncio
async def test_native_call_keeps_arguments_in_memory_roundtrip():
    from dbgpt.agent.core.memory.agent_memory import StructuredAgentMemoryFragment

    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    calls = [
        {
            "id": "call-1",
            "function": {
                "name": "add",
                "arguments": '{"a":2,"b":3,"intention":"calculate"}',
            },
        }
    ]
    kwargs = _act_kwargs(agent, False)
    kwargs["tool_calls"] = calls
    object.__setattr__(agent, "_pending_native_tool_calls", calls)
    out = await agent.act(AgentMessage(content=""), sender=agent, **kwargs)
    assert out.is_exe_success and out.content == "5"
    assert json.loads(out.action_input) == {"a": 2, "b": 3}
    memory = SimpleNamespace(
        write=AsyncMock(),
        read=AsyncMock(return_value=[]),
    )
    object.__setattr__(agent, "memory", memory)
    await agent.write_memories(
        question="compute",
        ai_message="",
        action_output=out,
        check_pass=True,
        current_retry_counter=0,
    )
    fragment = memory.write.call_args.args[0]
    assert isinstance(fragment, StructuredAgentMemoryFragment)
    memory.read.return_value = [fragment]
    restored = await agent.read_memories("continue")
    assert any(
        'Action Input: {"a": 2, "b": 3}' in (message.content or "")
        for message in restored
    )


@pytest.mark.asyncio
async def test_missing_arguments_stop_after_three_rounds_even_if_tool_changes():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    for index, name in enumerate(("add", "add", "multiply")):
        output = await agent.act(
            AgentMessage(content=f"Thought: execute.\nAction: {name}"),
            sender=agent,
            **_act_kwargs(agent, False),
        )
        assert not output.is_exe_success
        assert output.have_retry is (index < 2)
        if index < 2:
            assert "TOOL_ARGUMENT_INVALID" in output.content
            assert "a, b" in output.content
        else:
            assert "TOOL_PROTOCOL_RETRY_EXHAUSTED" in output.content
            passed, _ = await agent.verify(
                AgentMessage(content="", action_report=output), sender=agent
            )
            assert not passed and not output.terminate


@pytest.mark.asyncio
async def test_valid_call_resets_protocol_failure_budget():
    agent = _make_agent(enable_parallel=False)
    for _ in range(2):
        await agent.act(
            AgentMessage(content="Action: add"),
            sender=agent,
            **_act_kwargs(agent, False),
        )
    output = await agent.act(
        AgentMessage(content='Action: add\nAction Input: {"a":2,"b":3}'),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert output.is_exe_success and agent._tool_protocol_failures == 0
    output = await agent.act(
        AgentMessage(content="Action: add"),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert output.have_retry and agent._tool_protocol_failures == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ['{"a":', '["unexpected"]'])
async def test_malformed_native_arguments_never_execute_parameterless_tool(arguments):
    invoked = []

    @tool(description="Record a call")
    def record():
        invoked.append(True)
        return "ok"

    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    pack = ToolPack([record._tool])
    agent.resource = pack
    for action in agent.actions:
        action.init_resource(pack)
    calls = [{"function": {"name": "record", "arguments": arguments}}]
    object.__setattr__(agent, "_pending_native_tool_calls", calls)
    kwargs = _act_kwargs(agent, False)
    kwargs["tool_calls"] = calls
    output = await agent.act(AgentMessage(content=""), sender=agent, **kwargs)
    assert not invoked
    assert "TOOL_ARGUMENT_INVALID" in output.content


@pytest.mark.asyncio
async def test_protocol_repair_requests_native_function_and_keeps_arguments():
    from dbgpt.core import ModelOutput

    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    await agent.act(
        AgentMessage(content="Action: add"),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    calls = [
        {
            "id": "call-2",
            "function": {
                "name": "add",
                "arguments": '{"a":2,"b":3}',
            },
        }
    ]
    create = AsyncMock(return_value=ModelOutput.build("", tool_calls=calls))
    object.__setattr__(agent, "llm_client", SimpleNamespace(create_with_output=create))
    object.__setattr__(agent, "memory", SimpleNamespace(gpts_memory=None))
    object.__setattr__(
        agent, "_a_select_llm_model", AsyncMock(return_value="synthetic")
    )
    await agent.thinking([AgentMessage(role="human", content="continue")])
    assert create.call_args.kwargs["tool_choice"] == "required"
    kwargs = agent.prepare_act_param(None, agent)
    output = await agent.act(AgentMessage(content=""), sender=agent, **kwargs)
    assert output.is_exe_success and output.content == "5"


@pytest.mark.asyncio
async def test_generate_reply_stops_protocol_loop_before_sixty_step_budget():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    agent.max_retry_count = 60
    think = AsyncMock(return_value=("Thought: execute.\nAction: add", "synthetic"))
    execute = AsyncMock()
    object.__setattr__(agent, "thinking", think)
    object.__setattr__(
        agent, "_load_thinking_messages", AsyncMock(return_value=([], None))
    )
    object.__setattr__(agent, "review", AsyncMock(return_value=(True, None)))
    object.__setattr__(agent, "send", AsyncMock())
    object.__setattr__(agent, "write_memories", AsyncMock())
    object.__setattr__(agent, "adjust_final_message", AsyncMock())
    object.__setattr__(agent.resource, "async_execute", execute)
    reply = await agent.generate_reply(
        received_message=AgentMessage(content="compute"), sender=agent
    )
    assert think.await_count == 3
    execute.assert_not_awaited()
    assert reply.success is False
    assert reply.action_report.have_retry is False
    assert "TOOL_PROTOCOL_RETRY_EXHAUSTED" in reply.action_report.content
