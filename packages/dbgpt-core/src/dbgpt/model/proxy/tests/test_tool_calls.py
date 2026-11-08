"""Tests for streaming tool_calls merging (native function calling)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import BadRequestError

from dbgpt.model.proxy.llms.chatgpt import (
    OpenAILLMClient,
    merge_streaming_tool_calls,
)


def test_merge_single_tool_call_across_fragments():
    deltas = [
        {
            "index": 0,
            "id": "call_1",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a": '},
        },
        {"index": 0, "function": {"arguments": '1, "b": 2}'}},
    ]
    merged = merge_streaming_tool_calls(None, deltas)
    assert len(merged) == 1
    assert merged[0]["id"] == "call_1"
    assert merged[0]["function"]["name"] == "add"
    assert merged[0]["function"]["arguments"] == '{"a": 1, "b": 2}'


def test_merge_multiple_tool_calls_by_index():
    deltas = [
        {"index": 0, "id": "c0", "function": {"name": "add", "arguments": "{}"}},
        {
            "index": 1,
            "id": "c1",
            "function": {"name": "multiply", "arguments": '{"x":'},
        },
        {"index": 1, "function": {"arguments": "1}"}},
    ]
    merged = merge_streaming_tool_calls(None, deltas)
    assert [m["id"] for m in merged] == ["c0", "c1"]
    assert merged[1]["function"]["name"] == "multiply"
    assert merged[1]["function"]["arguments"] == '{"x":1}'


def test_merge_dict_arguments_stringified():
    deltas = [
        {
            "index": 0,
            "function": {"name": "f", "arguments": {"a": 1}},
        }
    ]
    merged = merge_streaming_tool_calls(None, deltas)
    assert merged[0]["function"]["arguments"] == '{"a": 1}'


def test_merge_none_deltas_noop():
    assert merge_streaming_tool_calls(None, None) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_required_tool_choice_retries_once_without_mutating_payload(stream):
    error = BadRequestError(
        "inference request is invalid",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://example.test/v1")
        ),
        body={"error": {"code": "invalid_request"}},
    )
    completion = object()
    create = AsyncMock(side_effect=[error, completion])
    client = OpenAILLMClient.__new__(OpenAILLMClient)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    payload = {
        "model": "compatible-model",
        "stream": stream,
        "tools": [{"type": "function"}],
        "tool_choice": "required",
    }
    messages = [{"role": "user", "content": "Use the supplied tool."}]
    assert await client._create_chat_completion(messages, payload) is completion
    assert create.await_count == 2
    assert create.await_args_list[0].kwargs["tool_choice"] == "required"
    assert create.await_args_list[1].kwargs == {
        **payload,
        "messages": messages,
        "tool_choice": "auto",
    }
    assert payload["tool_choice"] == "required"


@pytest.mark.asyncio
@pytest.mark.parametrize("choice", ["auto", "none"])
async def test_other_bad_requests_do_not_retry_tool_choice(choice):
    error = BadRequestError(
        "invalid request",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://example.test/v1")
        ),
        body={},
    )
    create = AsyncMock(side_effect=error)
    client = OpenAILLMClient.__new__(OpenAILLMClient)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with pytest.raises(BadRequestError):
        await client._create_chat_completion(
            [], {"tools": [{"type": "function"}], "tool_choice": choice}
        )
    assert create.await_count == 1


@pytest.mark.asyncio
async def test_required_tool_choice_fallback_failure_is_propagated():
    error = BadRequestError(
        "invalid request",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://example.test/v1")
        ),
        body={},
    )
    create = AsyncMock(side_effect=error)
    client = OpenAILLMClient.__new__(OpenAILLMClient)
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with pytest.raises(BadRequestError):
        await client._create_chat_completion(
            [], {"tools": [{"type": "function"}], "tool_choice": "required"}
        )
    assert create.await_count == 2
