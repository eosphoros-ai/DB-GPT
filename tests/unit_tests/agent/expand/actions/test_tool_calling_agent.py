"""Integration tests for ToolCallingReActAgent action dispatch.

These drive the agent's ``act()`` through the real ``ConversableAgent.act``
dispatch loop (the same loop ``generate_reply`` — and thus the
``/api/v1/chat/react-agent`` endpoint — uses) but with a stubbed resource, so
no LLM/network is required.
"""

import json

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
@pytest.mark.parametrize("report", [False, True])
@pytest.mark.parametrize("catalogue_reads", [0, 6])
async def test_report_requires_native_call_with_latest_progress_only(
    report, catalogue_reads
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from dbgpt.core import ModelOutput

    agent = _make_agent(enable_parallel=False)

    @tool(description="Read captured report objects")
    def list_report_objects() -> str:
        return "[]"

    agent.resource = ToolPack([add._tool, list_report_objects._tool])
    calls = [{"function": {"name": "add", "arguments": '{"a":1,"b":2}'}}]
    generate = AsyncMock(
        return_value=ModelOutput(error_code=0, text="", tool_calls=calls)
    )
    object.__setattr__(
        agent, "llm_client", SimpleNamespace(create_with_output=generate)
    )
    object.__setattr__(agent, "memory", SimpleNamespace(gpts_memory=None))
    object.__setattr__(
        agent, "_a_select_llm_model", AsyncMock(return_value="test-model")
    )
    state = {
        "_report_template_contract": {"prose_fields": ["SUMMARY", "ADVICE"]},
        "_report_object_fields": {"SUMMARY": "Validated summary"},
        "_report_html_error": "Correct the ADVICE field",
        "_report_catalogue_reads": catalogue_reads,
    }
    object.__setattr__(agent, "_report_repair_state", state)
    agent.agent_context.gpts_app_code = (
        "react_agent_report" if report else "react_agent"
    )
    for remaining in (["ADVICE"], []):
        if not remaining:
            state["_report_object_fields"]["ADVICE"] = "Validated advice"
        await agent._thinking_native([AgentMessage(content="Initial task snapshot")])
        request = generate.call_args.kwargs
        assert request["tool_choice"] == ("required" if report else "auto")
        offered = {item["function"]["name"] for item in request["tools"]}
        assert ("list_report_objects" not in offered) == (
            report and catalogue_reads >= 6
        )
        if report:
            progress = request["messages"][-1]["content"]
            assert json.dumps(remaining) in progress
            assert "Correct the ADVICE field" in progress
            assert "supersedes the initial handoff" in progress
        else:
            assert len(request["messages"]) == 1
        assert agent._pending_native_tool_calls == calls


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", " ", "\n\t"])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("parallel", [False, True])
async def test_empty_text_fallback_returns_controlled_failure(text, native, parallel):
    agent = _make_agent(enable_parallel=parallel)
    agent.agent_context.enable_native_function_calling = native
    out = await agent.act(
        AgentMessage(content=text),
        sender=agent,
        **_act_kwargs(agent, parallel),
    )
    assert out.is_exe_success is False
    assert out.terminate is not True
    assert out.content


@pytest.mark.asyncio
async def test_empty_text_with_native_call_still_executes():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    calls = [{"function": {"name": "add", "arguments": '{"a":1,"b":2}'}}]
    object.__setattr__(agent, "_pending_native_tool_calls", calls)
    kwargs = _act_kwargs(agent, False)
    kwargs["tool_calls"] = calls
    out = await agent.act(AgentMessage(content=""), sender=agent, **kwargs)
    assert out.is_exe_success, out.content
    assert "3" in out.observations


@pytest.mark.asyncio
async def test_text_batch_preparse_returns_parser_failure():
    from unittest.mock import MagicMock

    from dbgpt.agent.expand.tool_calling_agent import NativeToolCallAction
    from dbgpt.agent.util.react_parser import ReActOutputParser

    parser = MagicMock(spec=ReActOutputParser)
    parser.parse_current_step.side_effect = ValueError("Invalid text response")
    action = NativeToolCallAction()
    out = await action.run("invalid", parser=parser)
    assert out.is_exe_success is False
    assert out.content == "Invalid text response"


@pytest.mark.asyncio
async def test_native_fallback_executes_arguments_alias():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    out = await agent.act(
        AgentMessage(content='Action: add\nArguments: {"a":1,"b":2}'),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success, out.content
    assert out.action == "add"
    assert out.observations == "3"


@pytest.mark.asyncio
async def test_native_fallback_executes_bold_arguments_with_crlf_blank_line():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    out = await agent.act(
        AgentMessage(content='**Action**: add\r\n\r\n**Arguments**: {"a":1,"b":2}'),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success, out.content
    assert out.action == "add"
    assert out.observations == "3"


@pytest.mark.asyncio
async def test_native_fallback_preserves_explicit_text_batch_pairs():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    out = await agent.act(
        AgentMessage(
            content=(
                'Action: add, multiply\nAction Input: [{"a":1,"b":2},{"a":3,"b":4}]'
            )
        ),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success
    results = json.loads(out.observations)
    assert [r["name"] for r in results] == ["add", "multiply"]
    assert [r["observation"] for r in results] == ["3", "12"]


@pytest.mark.asyncio
async def test_native_fallback_rejects_ambiguous_batch_before_execution():
    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    out = await agent.act(
        AgentMessage(content='Action: add, multiply\nAction Input: [{"a":1,"b":2}]'),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert not out.is_exe_success
    assert "TOOL_BATCH_INVALID" in out.content


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["[]", "{}"])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("parallel", [False, True])
async def test_text_single_no_args_preserves_legacy_parsing(raw, native, parallel):
    from dbgpt.agent.expand.resources.host_tool import get_current_host_memory_status

    agent = _make_agent(enable_parallel=parallel)
    agent.agent_context.enable_native_function_calling = native
    agent.resource = ToolPack([get_current_host_memory_status._tool])
    for action in agent.actions:
        action.init_resource(agent.resource)
    out = await agent.act(
        AgentMessage(
            content=f"Action: get_current_host_memory_status\nAction Input: {raw}"
        ),
        sender=agent,
        **_act_kwargs(agent, parallel),
    )
    assert out.is_exe_success, out.content
    assert "Available:" in out.observations


@pytest.mark.asyncio
async def test_text_single_object_array_remains_supported():
    agent = _make_agent(enable_parallel=False)
    out = await agent.act(
        AgentMessage(content='Action: add\nAction Input: [{"a":1,"b":2}]'),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success, out.content
    assert "3" in out.observations


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["[]", "{}", '[{"a":1,"b":2}]'])
async def test_text_single_array_uses_custom_argument_parser(raw):
    from dbgpt.agent.resource.tool.base import FunctionTool

    parsed = []

    def parse_args(value):
        parsed.append(value)
        return (), {"a": 10, "b": 20}

    custom = FunctionTool(
        "custom_add",
        lambda a, b: a + b,
        description="Custom argument parser",
        parse_execute_args_func=parse_args,
    )
    agent = _make_agent(enable_parallel=False)
    agent.resource = ToolPack([custom])
    for action in agent.actions:
        action.init_resource(agent.resource)
    out = await agent.act(
        AgentMessage(content=f"Action: custom_add\nAction Input: {raw}"),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success, out.content
    assert len(parsed) == 1 and json.loads(parsed[0]) == json.loads(raw)
    assert out.observations == "30"


@pytest.mark.asyncio
async def test_compose_success_finishes_report_without_extra_model_turn():
    state = {"_report_lock_after_completion": True}

    @tool(description="Compose report")
    def compose_report(data: dict) -> str:
        state["_report_success_response"] = '{"status":"completed"}'
        return state["_report_success_response"]

    agent = _make_agent(enable_parallel=False)
    agent.agent_context.enable_native_function_calling = True
    agent.resource = ToolPack([compose_report._tool])
    for action in agent.actions:
        action.init_resource(agent.resource)
    object.__setattr__(agent, "_report_repair_state", state)
    out = await agent.act(
        AgentMessage(content='Action: compose_report\nAction Input: {"data":{}}'),
        sender=agent,
        **_act_kwargs(agent, False),
    )
    assert out.is_exe_success
    assert out.terminate


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["html_interpreter", "append_report_sections", "compose_report"]
)
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
