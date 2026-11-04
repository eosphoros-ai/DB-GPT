"""Tests for the Claude proxy LLM client."""

import pytest

from dbgpt.core import ModelRequest
from dbgpt.model.proxy.llms.claude import ClaudeLLMClient


@pytest.fixture
def client():
    return ClaudeLLMClient(api_key="test-key")


def test_constructor_sets_api_base_from_argument_or_default(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    assert ClaudeLLMClient(api_key="k")._api_base == "https://api.anthropic.com"
    custom = ClaudeLLMClient(api_key="k", api_base="https://claude.example.com")
    assert custom._api_base == "https://claude.example.com"


def test_client_builds_with_and_without_proxy():
    plain = ClaudeLLMClient(api_key="k").client
    assert plain.api_key == "k"
    proxied = ClaudeLLMClient(api_key="k", proxies="http://127.0.0.1:8080").client
    assert proxied.api_key == "k"


@pytest.mark.parametrize("stop, expected", [("END", ["END"]), (["a", "b"], ["a", "b"])])
def test_build_request_maps_stop_to_stop_sequences(client, stop, expected):
    request = ModelRequest(model="claude-3-5-sonnet-20241022", messages=[], stop=stop)
    payload = client._build_request(request)
    assert payload["stop_sequences"] == expected
    assert "stop" not in payload
