"""API Route configuration and HTTP header regression tests."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from dbgpt.core import ModelMessage, ModelRequest
from dbgpt.core.interface.message import ModelMessageRoleType
from dbgpt.model.proxy.llms.api_route import (
    API_ROUTE_HEADERS,
    ApiRouteDeployModelParameters,
    ApiRouteLLMClient,
    api_route_generate_stream,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.model.utils.chatgpt_utils import OpenAIParameters, _build_openai_client


@pytest.fixture(autouse=True)
def clear_api_route_environment(monkeypatch):
    monkeypatch.delenv("API_ROUTE_API_KEY", raising=False)
    monkeypatch.delenv("API_ROUTE_API_BASE", raising=False)


def test_missing_key_is_reported():
    with pytest.raises(ValueError, match="API_ROUTE_API_KEY"):
        ApiRouteLLMClient()


@pytest.mark.asyncio
async def test_environment_defaults(monkeypatch):
    monkeypatch.setenv("API_ROUTE_API_KEY", "environment-test-key")
    monkeypatch.setenv("API_ROUTE_API_BASE", "https://environment.example/v1")
    client = ApiRouteLLMClient()
    try:
        assert client.client.api_key == "environment-test-key"
        assert str(client.client.base_url) == "https://environment.example/v1/"
        assert client.default_model == "deepseek/deepseek-chat"
        assert client.context_length == 64_000
        assert all(
            client.client.default_headers[k] == v for k, v in API_ROUTE_HEADERS.items()
        )
    finally:
        await client.client.close()


@pytest.mark.asyncio
async def test_explicit_settings_override_environment(monkeypatch):
    monkeypatch.setenv("API_ROUTE_API_KEY", "environment-test-key")
    monkeypatch.setenv("API_ROUTE_API_BASE", "https://environment.example/v1")
    client = ApiRouteLLMClient(
        api_key="explicit-test-key",
        api_base="https://explicit.example/v1",
        model="custom-model",
        context_length=32_000,
        default_headers={"X-Title": "Custom app", "X-Custom": "custom-value"},
    )
    try:
        assert client.client.api_key == "explicit-test-key"
        assert str(client.client.base_url) == "https://explicit.example/v1/"
        assert client.default_model == "custom-model"
        assert client.model_names == ["custom-model"]
        assert [metadata.model for metadata in await client.models()] == [
            "custom-model"
        ]
        assert client.context_length == 32_000
        assert client.client.default_headers["X-Title"] == "Custom app"
        assert client.client.default_headers["X-Custom"] == "custom-value"
    finally:
        await client.client.close()


@pytest.mark.asyncio
async def test_explicit_model_alias_is_preserved():
    client = ApiRouteLLMClient(
        api_key="test-key", model="custom-model", model_alias="public-alias"
    )
    try:
        assert client.default_model == "custom-model"
        assert client.model_names == ["public-alias"]
        assert [metadata.model for metadata in await client.models()] == [
            "public-alias"
        ]
    finally:
        await client.client.close()


@pytest.mark.asyncio
async def test_attribution_headers_reach_requests_with_injected_client():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "hello"},
                    }
                ],
            },
        )

    injected = AsyncOpenAI(
        api_key="test-key",
        base_url="https://mock.example/v1",
        default_headers={"X-Custom": "preserved"},
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    client = ApiRouteLLMClient(api_key="test-key", openai_client=injected)
    try:
        await client.client.chat.completions.create(
            model="test-model", messages=[{"role": "user", "content": "hello"}]
        )
        assert len(requests) == 1
        for key, value in API_ROUTE_HEADERS.items():
            assert requests[0].headers[key] == value
        assert requests[0].headers["X-Custom"] == "preserved"
        assert "HTTP-Referer" not in injected.default_headers
    finally:
        await injected.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("use_wrapper", [False, True], ids=["client", "wrapper"])
async def test_provider_streaming_accumulates_model_output(use_wrapper):
    requests = []
    chunks = [
        {
            "id": "test-stream",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "custom-model",
            "choices": [
                {"index": 0, "delta": {"content": text}, "finish_reason": None}
            ],
        }
        for text in ["hello", " world"]
    ]
    chunks.append(
        {
            "id": "test-stream",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "custom-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            },
        }
    )
    events = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(events + "data: [DONE]\n\n").encode(),
        )

    injected = AsyncOpenAI(
        api_key="test-key",
        base_url="https://mock.example/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    client = ApiRouteLLMClient(
        api_key="test-key", model="custom-model", openai_client=injected
    )
    messages = [ModelMessage(role=ModelMessageRoleType.HUMAN, content="hello")]
    try:
        if use_wrapper:
            model = ProxyModel(
                ApiRouteDeployModelParameters(name="custom-model"),
                proxy_llm_client=client,
            )
            stream = api_route_generate_stream(
                model, None, {"messages": messages, "max_new_tokens": 10}, "cpu"
            )
        else:
            stream = client.generate_stream(
                ModelRequest(model="custom-model", messages=messages, max_new_tokens=10)
            )
        outputs = [output async for output in stream]
        assert [output.text for output in outputs] == [
            "hello",
            "hello world",
            "hello world",
        ]
        assert all(output.error_code == 0 for output in outputs)
        expected_usage = {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        }
        assert outputs[-1].usage is not None
        for key, value in expected_usage.items():
            assert outputs[-1].usage[key] == value
        assert len(requests) == 1
        assert requests[0].url.path == "/v1/chat/completions"
        payload = json.loads(requests[0].content)
        assert payload["stream"] is True
        assert payload["model"] == "custom-model"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["max_tokens"] == 10
        for key, value in API_ROUTE_HEADERS.items():
            assert requests[0].headers[key] == value
    finally:
        await injected.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("api_type", ["open_ai", "azure"])
async def test_shared_builder_persists_headers(api_type):
    _, client = _build_openai_client(
        OpenAIParameters(
            api_type=api_type,
            api_key="test-key",
            api_base="https://test.example/v1",
            api_version="2024-02-01",
        ),
        default_headers=API_ROUTE_HEADERS,
    )
    try:
        assert all(client.default_headers[k] == v for k, v in API_ROUTE_HEADERS.items())
    finally:
        await client.close()
