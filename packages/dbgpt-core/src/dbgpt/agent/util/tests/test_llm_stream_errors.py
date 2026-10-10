"""Model error chunks must fail inference, not become successful agent answers."""

from unittest.mock import AsyncMock

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.agent.util.llm.llm_client import AIWrapper
from dbgpt.core import ModelOutput
from dbgpt.util.error_types import LLMChatError


class StreamingClient:
    def __init__(self, attempts):
        self.attempts = iter(attempts)
        self.requests = []

    async def generate_stream(self, request):
        self.requests.append(request)
        for output in next(self.attempts):
            yield output


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["create", "create_with_output"])
async def test_error_chunk_is_not_emitted_as_answer_or_saved_to_memory(method):
    client = StreamingClient(
        [
            [
                ModelOutput(text="partial", error_code=0),
                ModelOutput(text="timeout", error_code=1),
            ]
        ]
    )
    memory = AsyncMock()
    callback = AsyncMock()
    with pytest.raises(LLMChatError, match="timeout"):
        await getattr(AIWrapper(client), method)(
            messages=[{"role": "human", "content": "Test"}],
            llm_model="test",
            max_new_tokens=100,
            temperature=0,
            memory=memory,
            stream_callback=callback,
        )
    assert callback.await_count == 1
    assert callback.call_args.args[0]["delta_text"] == "partial"
    assert memory.push_message.await_count == 1
    assert memory.push_message.call_args.args[1]["markdown"] == "partial"


@tool(description="A tool that must not run during inference retries")
def probe() -> str:
    raise AssertionError("Inference must not execute tools")


@pytest.mark.asyncio
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("recovers", [False, True])
async def test_agent_retries_only_inference_and_propagates_exhaustion(
    monkeypatch, native, recovers
):
    error = ModelOutput(text="model timed out", error_code=1)
    success = ModelOutput(text="Recovered answer", error_code=0)
    client = StreamingClient([[error], [success]] if recovers else [[error]] * 3)
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="stream-error-test", enable_native_function_calling=native
    )
    agent.llm_client = AIWrapper(client)
    agent.stream_out = False
    agent.resource = ToolPack([probe._tool])
    monkeypatch.setattr(
        ToolCallingReActAgent, "_a_select_llm_model", AsyncMock(return_value="test")
    )
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    messages = [AgentMessage(content="Test", role="human")]
    if recovers:
        answer, model = await agent.thinking(messages)
        assert (answer, model) == ("Recovered answer", "test")
        assert len(client.requests) == 2
    else:
        with pytest.raises(ValueError, match="model timed out"):
            await agent.thinking(messages)
        assert len(client.requests) == 3
    assert getattr(agent, "_pending_native_tool_calls", None) is None
