"""All built-in thinking paths budget the model selected for that request."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from dbgpt.agent import AgentContext, AgentMessage, LLMConfig, ProfileConfig
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.expand.react_agent import ReActAgent
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.core import LLMClient, ModelMetadata, ModelOutput


def make_agent(agent_type, *, cap=0):
    metadata = {
        "small": ModelMetadata(
            model="small", context_length=16000, max_output_length=7000
        ),
        "large": ModelMetadata(model="large", context_length=128000),
        "unknown": ModelMetadata(model="unknown", context_length=None),
    }
    client = MagicMock(spec=LLMClient)
    client.get_model_metadata = AsyncMock(side_effect=lambda name: metadata[name])
    kwargs = (
        {"profile": ProfileConfig(name="test", role="test")}
        if agent_type is ConversableAgent
        else {}
    )
    agent = agent_type(**kwargs).bind(
        AgentContext(conv_id="budget-test", max_context_tokens=cap, max_new_tokens=6000)
    )
    agent.bind(LLMConfig(llm_client=client))
    return agent, client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_type", [ConversableAgent, ReActAgent, ToolCallingReActAgent]
)
async def test_switching_models_recomputes_isolated_budget(agent_type):
    agent, client = make_agent(agent_type)
    other, _ = make_agent(agent_type)
    messages = [AgentMessage(content="question")]
    await agent._manage_model_context(messages, "small")
    manager = agent._context_manager
    assert manager.config.model_context_tokens == 16000
    assert manager.config.effective_budget == 10000
    assert other._context_manager is None
    await agent._manage_model_context(messages, "small")
    assert client.get_model_metadata.await_count == 1
    await agent._manage_model_context(messages, "large")
    assert manager.config.max_context_tokens == 128000
    assert manager.tracker.model_name == "large"
    await agent._manage_model_context(messages, "unknown")
    assert manager.config.model_context_tokens is None
    assert manager.config.context_window_source == "fallback"
    assert manager.config.max_context_tokens == 120000


@pytest.mark.asyncio
async def test_explicit_cap_and_output_reservation_are_preserved():
    agent, _ = make_agent(ConversableAgent, cap=12000)
    await agent._manage_model_context([AgentMessage(content="question")], "large")
    config = agent._context_manager.config
    assert config.max_context_tokens == 12000
    assert config.context_window_source == "agent_config"
    agent.agent_context.max_new_tokens = 8000
    await agent._manage_model_context([AgentMessage(content="question")], "large")
    assert config.reserved_tokens == 8000
    assert config.effective_budget == 4000


@pytest.mark.asyncio
@pytest.mark.parametrize("native", [False, True])
async def test_request_boundary_counts_prompt_input_and_native_schema(native):
    agent, _ = make_agent(ToolCallingReActAgent if native else ConversableAgent)
    agent.agent_context.enable_native_function_calling = native

    @tool(description="Calculate a value")
    def calculate(value: int) -> int:
        return value + 1

    agent.resource = ToolPack([calculate])
    object.__setattr__(agent, "_a_select_llm_model", AsyncMock(return_value="small"))
    create = AsyncMock(
        return_value=ModelOutput(text="answer", error_code=0) if native else "answer"
    )
    object.__setattr__(
        agent,
        "llm_client",
        SimpleNamespace(create_with_output=create, create=create),
    )
    answer, model = await agent.thinking(
        [AgentMessage(content="current input")], prompt="system rules"
    )
    assert answer == "answer" and model == "small"
    request = create.call_args.kwargs
    assert any("system rules" in item["content"] for item in request["messages"])
    assert any("current input" in item["content"] for item in request["messages"])
    manager = agent._context_manager
    assert manager.config.effective_budget == 10000
    assert (manager.tracker.extra_tokens > 0) is native


@pytest.mark.asyncio
async def test_explicit_opt_out_is_respected():
    agent, client = make_agent(ConversableAgent)
    agent.agent_context.enable_context_management = False
    messages = [AgentMessage(content="question")]
    assert await agent._manage_model_context(messages, "small") is messages
    assert agent._context_manager is None
    client.get_model_metadata.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_output_is_capped_by_model_metadata():
    agent, _ = make_agent(ReActAgent)
    agent.agent_context.max_new_tokens = 9000
    await agent._manage_model_context([AgentMessage(content="question")], "small")
    assert agent._request_max_new_tokens() == 7000
    assert agent._context_manager.config.reserved_tokens == 7000
    await agent._manage_model_context([AgentMessage(content="question")], "large")
    assert agent._request_max_new_tokens() == 9000
    await agent._manage_model_context([AgentMessage(content="question")], "small")
    assert agent._context_manager.config.reserved_tokens == 7000
