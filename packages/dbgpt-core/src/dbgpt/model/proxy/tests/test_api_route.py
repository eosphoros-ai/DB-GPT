"""API Route configuration and HTTP header regression tests."""

import httpx
import pytest
from openai import AsyncOpenAI

from dbgpt.model.proxy.llms.api_route import API_ROUTE_HEADERS, ApiRouteLLMClient
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
        assert client.context_length == 32_000
        assert client.client.default_headers["X-Title"] == "Custom app"
        assert client.client.default_headers["X-Custom"] == "custom-value"
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
