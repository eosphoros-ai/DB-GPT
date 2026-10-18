"""Integration tests for ToolCallingReActAgent action dispatch.

These drive the agent's ``act()`` through the real ``ConversableAgent.act``
dispatch loop (the same loop ``generate_reply`` — and thus the
``/api/v1/chat/react-agent`` endpoint — uses) but with a stubbed resource, so
no LLM/network is required.
"""

import json

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
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
