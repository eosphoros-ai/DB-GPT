"""Tests for the Gemini proxy LLM client."""

from unittest.mock import MagicMock, patch

import pytest

from dbgpt.core import ModelMessage, ModelMessageRoleType, ModelRequest
from dbgpt.model.proxy.llms.gemini import GeminiLLMClient


def _generation_config(request: ModelRequest) -> dict:
    import google.generativeai as genai

    client = GeminiLLMClient(model="gemini-2.0-flash", api_key="test-key")
    chunk = MagicMock()
    chunk.text = "ok"
    chat = MagicMock()
    chat.send_message.return_value = [chunk]
    model_cls = MagicMock()
    model_cls.return_value.start_chat.return_value = chat
    with patch.object(genai, "GenerativeModel", model_cls):
        outputs = list(client.sync_generate_stream(request))
    assert outputs[-1].error_code == 0, outputs[-1].text
    return model_cls.call_args.kwargs["generation_config"]


def _request(**kwargs) -> ModelRequest:
    return ModelRequest(
        model="gemini-2.0-flash",
        messages=[ModelMessage(role=ModelMessageRoleType.HUMAN, content="hi")],
        **kwargs,
    )


@pytest.mark.parametrize("top_p", [0.2, 0.9])
def test_user_top_p_is_forwarded(top_p):
    config = _generation_config(_request(temperature=0.7, top_p=top_p))
    assert config["temperature"] == 0.7
    assert config["top_p"] == top_p


def test_top_p_omitted_when_unset():
    config = _generation_config(_request(temperature=0.7))
    assert "top_p" not in config


def test_top_k_is_not_forced_to_greedy():
    config = _generation_config(_request(temperature=1.0, top_p=0.95))
    assert "top_k" not in config
