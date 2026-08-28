"""Tests for ReAct agent stream terminal-event lifecycle handling."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1 import agentic_data_api
from dbgpt_app.openapi.api_v1.react_final import AgentFinalAnswer


def _decode_sse_event(event: str):
    assert event.startswith("data: ")
    return json.loads(event.removeprefix("data: ").strip())


def test_history_failure_does_not_drop_final_or_done(caplog) -> None:
    class _FailingStorageConversation:
        def add_view_message(self, payload: str) -> None:
            raise RuntimeError("history storage unavailable")

        def end_current_round(self) -> None:
            raise AssertionError("must stop after the first persistence failure")

        def save_to_storage(self) -> None:
            raise AssertionError("must stop after the first persistence failure")

    events = agentic_data_api._react_terminal_events(
        _FailingStorageConversation(),
        '{"type":"react-agent"}',
        AgentFinalAnswer(content="answer"),
    )

    assert [_decode_sse_event(event) for event in events] == [
        {
            "type": "final",
            "protocol_version": 2,
            "content": "answer",
            "citations": [],
        },
        {"type": "done"},
    ]
    assert "Failed to persist ReAct agent history" in caplog.text


@pytest.mark.asyncio
async def test_closing_stream_cancels_and_awaits_agent_task(monkeypatch) -> None:
    task_started = asyncio.Event()
    task_finished = asyncio.Event()
    created_tasks = []

    async def _agent_work() -> None:
        task_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            task_finished.set()

    async def _fake_stream_impl(dialogue, tool_mode="full", agent_task_holder=None):
        del dialogue, tool_mode
        task = asyncio.create_task(_agent_work())
        created_tasks.append(task)
        agent_task_holder.append(task)
        await task_started.wait()
        yield "data: first\n\n"
        await asyncio.Event().wait()

    monkeypatch.setattr(
        agentic_data_api,
        "_react_agent_stream_impl",
        _fake_stream_impl,
    )

    stream = agentic_data_api._react_agent_stream(SimpleNamespace())
    assert await anext(stream) == "data: first\n\n"

    await stream.aclose()

    assert len(created_tasks) == 1
    assert created_tasks[0].cancelled()
    assert created_tasks[0].done()
    assert task_finished.is_set()


@pytest.mark.asyncio
async def test_runtime_failure_emits_structured_final_and_done(
    monkeypatch, caplog
) -> None:
    async def _failing_stream_impl(dialogue, tool_mode="full", agent_task_holder=None):
        del dialogue, tool_mode, agent_task_holder
        if False:
            yield ""
        raise RuntimeError("model stream failed")

    monkeypatch.setattr(
        agentic_data_api,
        "_react_agent_stream_impl",
        _failing_stream_impl,
    )

    events = [
        _decode_sse_event(event)
        async for event in agentic_data_api._react_agent_stream(SimpleNamespace())
    ]

    assert events == [
        {
            "type": "final",
            "protocol_version": 2,
            "content": "抱歉，回答生成过程中发生错误，请重试。",
            "citations": [],
        },
        {"type": "done"},
    ]
    assert "ReAct agent stream failed before normal completion" in caplog.text


@pytest.mark.asyncio
async def test_runtime_failure_does_not_duplicate_a_final_event(monkeypatch) -> None:
    async def _partially_failing_stream_impl(
        dialogue, tool_mode="full", agent_task_holder=None
    ):
        del dialogue, tool_mode, agent_task_holder
        yield agentic_data_api._sse_event(
            AgentFinalAnswer(content="answer").to_sse_payload()
        )
        raise RuntimeError("failed after final")

    monkeypatch.setattr(
        agentic_data_api,
        "_react_agent_stream_impl",
        _partially_failing_stream_impl,
    )

    events = [
        _decode_sse_event(event)
        async for event in agentic_data_api._react_agent_stream(SimpleNamespace())
    ]

    assert [event["type"] for event in events] == ["final", "done"]
    assert events[0]["content"] == "answer"


@pytest.mark.asyncio
async def test_response_disconnect_closes_stream_and_agent_task(monkeypatch) -> None:
    task_started = asyncio.Event()
    task_finished = asyncio.Event()
    body_send_started = asyncio.Event()
    never = asyncio.Event()
    created_tasks = []

    async def _agent_work() -> None:
        task_started.set()
        try:
            await never.wait()
        finally:
            task_finished.set()

    async def _fake_stream_impl(dialogue, tool_mode="full", agent_task_holder=None):
        del dialogue, tool_mode
        task = asyncio.create_task(_agent_work())
        created_tasks.append(task)
        agent_task_holder.append(task)
        await task_started.wait()
        yield agentic_data_api._sse_event({"type": "step", "content": "first"})
        await never.wait()

    async def _send(message) -> None:
        if message["type"] == "http.response.body" and message.get("more_body"):
            body_send_started.set()
            await never.wait()

    async def _receive():
        await body_send_started.wait()
        return {"type": "http.disconnect"}

    monkeypatch.setattr(
        agentic_data_api,
        "_react_agent_stream_impl",
        _fake_stream_impl,
    )
    response = agentic_data_api._AgentStreamingResponse(
        agentic_data_api._react_agent_stream(SimpleNamespace()),
        media_type="text/event-stream",
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/react-agent",
        "headers": [],
        "asgi": {"version": "3.0", "spec_version": "2.0"},
    }

    await asyncio.wait_for(response(scope, _receive, _send), timeout=1)

    assert len(created_tasks) == 1
    assert created_tasks[0].cancelled()
    assert created_tasks[0].done()
    assert task_finished.is_set()
