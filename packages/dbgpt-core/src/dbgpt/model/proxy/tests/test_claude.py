"""Tests for the Claude proxy LLM client."""

import os
from unittest.mock import patch

from dbgpt.model.proxy.llms.claude import DEFAULT_CLAUDE_MODEL, ClaudeLLMClient


class TestClaudeClientDefaults:
    """The client can be built and defaults to a model that is still served."""

    def test_client_without_configured_model_uses_the_default(self):
        client = ClaudeLLMClient(api_key="test-key")

        assert DEFAULT_CLAUDE_MODEL == "claude-sonnet-4-6"
        assert client.default_model == "claude-sonnet-4-6"
        assert client._model == "claude-sonnet-4-6"

    def test_configured_model_is_kept(self):
        client = ClaudeLLMClient(api_key="test-key", model="claude-haiku-4-5-20251001")

        assert client.default_model == "claude-haiku-4-5-20251001"

    def test_api_base_comes_from_the_argument_or_the_environment(self):
        client = ClaudeLLMClient(api_key="test-key", api_base="https://claude.example")
        assert client._api_base == "https://claude.example"

        with patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "https://env.example"}):
            client = ClaudeLLMClient(api_key="test-key")
        assert client._api_base == "https://env.example"


class TestClaudeModelRegistration:
    def test_default_model_is_registered_with_metadata(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter("proxy/claude", DEFAULT_CLAUDE_MODEL)
        assert adapter is not None

        metadata = {
            name: m
            for m in adapter.supported_models()
            for name in ([m.model] if isinstance(m.model, str) else m.model)
        }
        sonnet = metadata[DEFAULT_CLAUDE_MODEL]
        assert sonnet.context_length == 1024 * 1024
        assert sonnet.max_output_length == 128 * 1024
        assert sonnet.function_calling is True
        assert metadata["claude-opus-4-6"].context_length == 1024 * 1024
        assert metadata["claude-haiku-4-5-20251001"].context_length == 200 * 1024
