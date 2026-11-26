from unittest.mock import MagicMock

import pytest

from dbgpt.core import ModelRequest
from dbgpt.model.proxy.llms.xm4 import (
    XM4_API_BASE,
    XM4_MODELS,
    Xm4DeployModelParameters,
    Xm4LLMClient,
    list_xm4_models,
)
from dbgpt.model.utils.provider_test import _build_test_request


def test_gateway_probe_uses_default_url():
    url, headers = _build_test_request("proxy/xm4", "test-key", None)
    assert url == f"{XM4_API_BASE}/models"
    assert headers == {"Authorization": "Bearer test-key"}


def test_new_client_uses_model_context(monkeypatch):
    captured = {}

    def fake_init(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(Xm4LLMClient, "__init__", fake_init)
    Xm4LLMClient.new_client(
        Xm4DeployModelParameters(
            name="gpt-6", api_key="test-key", reasoning_effort="max"
        )
    )
    assert captured["context_length"] == 1_050_000
    assert captured["model"] == "gpt-6"
    assert captured["openai_kwargs"] == {"reasoning_effort": "max"}


def test_unsupported_variant_rejected():
    with pytest.raises(ValueError, match="Unsupported XM4 reasoning variant"):
        Xm4LLMClient.new_client(
            Xm4DeployModelParameters(
                name="codex-mini-latest", api_key="test-key", reasoning_effort="max"
            )
        )


@pytest.mark.parametrize("stream", [False, True])
def test_request_defaults_preserve_tools_and_limit_budget(stream):
    client = Xm4LLMClient(
        api_key="test-key",
        model="gpt-5.3-codex-spark",
        openai_client=MagicMock(),
        openai_kwargs={"store": True, "reasoning_effort": "high"},
    )
    tools = [{"type": "function", "function": {"name": "lookup", "parameters": {}}}]
    payload = client._build_request(
        ModelRequest(
            model="gpt-5.3-codex-spark",
            messages=[],
            max_new_tokens=128_000,
            temperature=0.7,
            top_p=0.9,
            tools=tools,
            tool_choice="auto",
        ),
        stream=stream,
    )
    assert payload["store"] is False
    assert payload["max_completion_tokens"] == 32_000
    assert payload["reasoning_effort"] == "high"
    assert payload["tools"] == tools
    assert payload["tool_choice"] == "auto"
    assert payload["stream"] is stream
    assert "max_tokens" not in payload
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_catalog_has_gateway_models_and_special_limits():
    catalog = {model.model: model for model in XM4_MODELS}
    assert len(catalog) == 14
    assert catalog["gpt-5.4-mini"].context_length == 400_000
    assert catalog["codex-mini-latest"].max_output_length == 100_000
    assert catalog["gpt-6-luna"].metadata["reasoning_variants"][0] == "none"


def test_domestic_model_preserves_sampling_and_token_budget():
    client = Xm4LLMClient(api_key="test-key", openai_client=MagicMock())
    payload = client._build_request(
        ModelRequest(
            model="deepseek-v4.1-flash",
            messages=[],
            max_new_tokens=1024,
            temperature=0.7,
            top_p=0.9,
        )
    )
    assert payload["max_tokens"] == 1024
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["store"] is False
    assert "max_completion_tokens" not in payload
    assert payload["extra_body"]["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_discovery_follows_key_group_and_keeps_unknown_limits(monkeypatch):
    import httpx

    async def fake_get(self, url, **kwargs):
        assert url == f"{XM4_API_BASE}/models"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={"data": [{"id": "deepseek-v4.1-flash"}, {"id": "glm-5.3-flash"}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    models = await list_xm4_models("test-key", XM4_API_BASE)
    assert [m.model for m in models] == ["deepseek-v4.1-flash", "glm-5.3-flash"]
    assert all(m.context_length is None for m in models)
