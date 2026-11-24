"""Tests for the OpenAI-compatible proxy request payload."""

import pytest

from dbgpt.core import ModelMessage, ModelRequest
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient


def _build_payload(**kwargs):
    client = OpenAILLMClient(api_key="test-key", model="gpt-4o-mini")
    request = ModelRequest(
        model="gpt-4o-mini",
        messages=[ModelMessage(role="user", content="hi")],
        **kwargs,
    )
    return client._build_request(request)


@pytest.mark.parametrize("value", [0, 0.0, 0.5])
def test_build_request_keeps_explicit_temperature_and_top_p(value):
    payload = _build_payload(temperature=value, top_p=value)

    assert payload["temperature"] == value
    assert payload["top_p"] == value


def test_build_request_omits_unset_temperature_and_top_p():
    payload = _build_payload()

    assert "temperature" not in payload
    assert "top_p" not in payload
