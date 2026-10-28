"""The pi loopback model API keeps reasoning separate from public text."""

import json
from types import SimpleNamespace

import pytest

from dbgpt.core.interface.llm import ModelOutput
from dbgpt_app.openapi.api_v2 import (
    _agentic_message_content,
    _agentic_out_text,
    agentic_chat_completions,
)


def test_public_text_excludes_thinking_blocks():
    output = ModelOutput.build("公开答复", "private reasoning")
    assert _agentic_out_text(output.content) == "公开答复"
    assert _agentic_out_text(ModelOutput.build_thinking("private").content) == ""
    assert (
        _agentic_message_content(
            [
                {"type": "thinking", "thinking": "private"},
                {"type": "text", "text": "答复"},
            ]
        )
        == "答复"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_model_api_separates_reasoning_and_text(monkeypatch, stream):
    from dbgpt.model.cluster.client import DefaultLLMClient

    async def generate(self, request):
        return ModelOutput.build("公开答复", "private reasoning")

    async def generate_stream(self, request):
        yield ModelOutput.build_thinking("private")
        yield ModelOutput.build_thinking("private reasoning")
        yield ModelOutput.build("公开", "private reasoning")
        yield ModelOutput.build("公开答复", "private reasoning", finish_reason="stop")

    monkeypatch.setattr(DefaultLLMClient, "generate", generate)
    monkeypatch.setattr(DefaultLLMClient, "generate_stream", generate_stream)
    service = SimpleNamespace(
        system_app=SimpleNamespace(
            get_component=lambda *args: SimpleNamespace(create=lambda: None)
        )
    )
    response = await agentic_chat_completions(
        {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": stream,
        },
        service,
    )
    if not stream:
        message = response["choices"][0]["message"]
        assert message["content"] == "公开答复"
        assert message["reasoning_content"] == "private reasoning"
        return
    deltas = []
    async for frame in response.body_iterator:
        payload = frame.removeprefix("data: ").strip()
        if payload != "[DONE]":
            deltas.append(json.loads(payload)["choices"][0]["delta"])
    assert "".join(delta.get("content", "") for delta in deltas) == "公开答复"
    assert (
        "".join(delta.get("reasoning_content", "") for delta in deltas)
        == "private reasoning"
    )
    assert all("private" not in delta.get("content", "") for delta in deltas)


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_native_tool_conversation_keeps_user_before_results(monkeypatch, stream):
    from dbgpt.model.cluster.client import DefaultLLMClient

    class Manager:
        async def generate(self, request):
            assert [message["role"] for message in request["messages"]] == [
                "system",
                "human",
                "ai",
                "tool",
            ]
            return ModelOutput.build("done")

        async def generate_stream(self, request):
            yield await self.generate(request)

    monkeypatch.setattr(
        DefaultLLMClient,
        "models",
        lambda self: pytest.fail("Native messages must not enter the scene converter"),
    )
    service = SimpleNamespace(
        system_app=SimpleNamespace(
            get_component=lambda *args: SimpleNamespace(create=lambda: Manager())
        )
    )
    response = await agentic_chat_completions(
        {
            "model": "test",
            "stream": stream,
            "messages": [
                {"role": "system", "content": "use tools"},
                {"role": "user", "content": "create a report"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "a",
                            "type": "function",
                            "function": {"name": "generate_report", "arguments": "{}"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "a", "content": "completed"},
            ],
        },
        service,
    )
    if stream:
        assert [frame async for frame in response.body_iterator]
    else:
        assert response["choices"][0]["message"]["content"] == "done"
