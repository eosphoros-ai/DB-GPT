"""Tests for the Y-API proxy LLM client."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dbgpt.core import ModelMessage, ModelRequest
from dbgpt.model.proxy.llms.y_api import (
    _YAPI_DEFAULT_MODEL,
    YApiDeployModelParameters,
    YApiLLMClient,
)


class _FakeCompletions:
    """Stands in for ``AsyncOpenAI.chat.completions``."""

    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    async def create(self, messages, **payload):
        self.calls.append(payload)

        async def _iter():
            for chunk in self._chunks:
                yield chunk

        return _iter()


class _FakeOpenAIClient:
    """Minimal OpenAI client: the base class only touches ``default_headers``
    and ``chat.completions.create``."""

    def __init__(self, chunks=()):
        self.default_headers = {}
        self.chat = SimpleNamespace(completions=_FakeCompletions(list(chunks)))


def _text_chunk(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))],
        usage=None,
    )


@pytest.fixture
def api_key():
    with patch.dict(os.environ, {"YAPI_API_KEY": "test-key"}):
        yield


class TestYApiDefaults:
    """Default model, endpoint and headers."""

    def test_default_model_is_vendor_prefixed(self):
        assert _YAPI_DEFAULT_MODEL == "deepseek/deepseek-v4-flash"

    def test_client_default_model(self, api_key):
        client = YApiLLMClient(openai_client=_FakeOpenAIClient())
        assert client.default_model == "deepseek/deepseek-v4-flash"

    def test_api_base_defaults_to_the_gateway(self, api_key):
        client = YApiLLMClient(openai_client=_FakeOpenAIClient())
        assert "api.y-api.bestvirtualgoods.com" in client._init_params.api_base

    def test_env_api_base_is_honoured(self, api_key):
        with patch.dict(os.environ, {"YAPI_API_BASE": "https://example.test/v1"}):
            client = YApiLLMClient(openai_client=_FakeOpenAIClient())
        assert client._init_params.api_base == "https://example.test/v1"

    def test_attribution_headers_are_installed(self, api_key):
        client = YApiLLMClient(openai_client=_FakeOpenAIClient())
        headers = client.client.default_headers
        assert headers["HTTP-Referer"] == "https://github.com/eosphoros-ai/DB-GPT"
        assert headers["X-Title"] == "DB GPT"


class TestYApiApiKey:
    """A missing key must fail loudly, at construction time."""

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Y-API key is required"):
                YApiLLMClient(openai_client=_FakeOpenAIClient())

    def test_key_from_argument_is_enough(self):
        with patch.dict(os.environ, {}, clear=True):
            client = YApiLLMClient(
                api_key="passed-in", openai_client=_FakeOpenAIClient()
            )
        assert client is not None


class TestYApiVendorPrefixedModelIds:
    """Y-API is a gateway, so the vendor prefix is part of the model id and
    must survive all the way into the outgoing payload."""

    @pytest.mark.parametrize(
        "model",
        [
            "deepseek/deepseek-v4-flash",
            "z-ai/glm-5.3",
            "moonshotai/kimi-k3",
            "openai/gpt-5.6-sol",
        ],
    )
    def test_model_id_reaches_the_payload_intact(self, api_key, model):
        client = YApiLLMClient(model=model, openai_client=_FakeOpenAIClient())
        request = ModelRequest(
            model=model, messages=[ModelMessage(role="user", content="hi")]
        )

        payload = client._build_request(request)

        assert payload["model"] == model

    def test_unknown_model_falls_back_to_the_default(self, api_key):
        client = YApiLLMClient(openai_client=_FakeOpenAIClient())
        request = ModelRequest(
            model="", messages=[ModelMessage(role="user", content="hi")]
        )

        payload = client._build_request(request)

        assert payload["model"] == _YAPI_DEFAULT_MODEL


class TestYApiContextLength:
    """The 128K fallback, and the factory path that has to preserve it."""

    def test_fallback_applies_when_omitted(self, api_key):
        client = YApiLLMClient(openai_client=_FakeOpenAIClient())
        assert client.context_length == 128 * 1024

    def test_explicit_value_wins(self, api_key):
        client = YApiLLMClient(
            context_length=262_144, openai_client=_FakeOpenAIClient()
        )
        assert client.context_length == 262_144

    def test_new_client_preserves_the_fallback(self, api_key):
        """``OpenAILLMClient.new_client`` clamps with
        ``max(context_length or 8192, 8192)``, which would silently replace the
        fallback with 8192 — the override has to keep the fallback reachable."""
        params = YApiDeployModelParameters(name="y-api-test")

        client = YApiLLMClient.new_client(params)

        assert client.context_length == 128 * 1024

    def test_new_client_keeps_an_explicit_value(self, api_key):
        params = YApiDeployModelParameters(name="y-api-test", context_length=1_048_576)

        client = YApiLLMClient.new_client(params)

        assert client.context_length == 1_048_576


class TestYApiStreaming:
    """Async streaming over the OpenAI-compatible endpoint."""

    def _request(self, model="deepseek/deepseek-v4-flash"):
        return ModelRequest(
            model=model, messages=[ModelMessage(role="user", content="hi")]
        )

    def test_stream_yields_incremental_text(self, api_key):
        fake = _FakeOpenAIClient([_text_chunk("He"), _text_chunk("llo")])
        client = YApiLLMClient(openai_client=fake)

        async def run():
            return [output async for output in client.generate_stream(self._request())]

        outputs = asyncio.run(run())

        assert [o.text for o in outputs] == ["He", "Hello"]
        assert all(o.error_code == 0 for o in outputs)

    def test_stream_requests_stream_true(self, api_key):
        fake = _FakeOpenAIClient([_text_chunk("hi")])
        client = YApiLLMClient(openai_client=fake)

        async def run():
            return [o async for o in client.generate_stream(self._request())]

        asyncio.run(run())

        assert fake.chat.completions.calls[0]["stream"] is True

    def test_stream_keeps_the_vendor_prefixed_model(self, api_key):
        fake = _FakeOpenAIClient([_text_chunk("hi")])
        client = YApiLLMClient(openai_client=fake)

        async def run():
            return [
                o async for o in client.generate_stream(self._request("z-ai/glm-5.3"))
            ]

        asyncio.run(run())

        assert fake.chat.completions.calls[0]["model"] == "z-ai/glm-5.3"
