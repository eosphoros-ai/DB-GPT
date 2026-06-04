"""Tests for DeepSeek proxy LLM client."""

import os
from unittest.mock import patch

from dbgpt.core import ModelMessage, ModelOutput, ModelRequest
from dbgpt.model.proxy.llms.deepseek import DeepseekLLMClient


class TestDeepSeekModelRegistration:
    """DeepSeek provider/model adapter resolution."""

    def test_supported_models_contains_v4_pro_metadata(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter("proxy/deepseek", "deepseek-v4-pro")
        assert adapter is not None

        metadata = {metadata.model: metadata for metadata in adapter.supported_models()}
        v4_pro = metadata["deepseek-v4-pro"]

        assert v4_pro.context_length == 1024 * 1024
        assert v4_pro.max_output_length == 384 * 1024
        assert v4_pro.function_calling is True


class TestDeepSeekContextLength:
    """DeepSeek model context length defaults."""

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"})
    def test_v4_pro_uses_one_million_context(self):
        client = DeepseekLLMClient(
            model="deepseek-v4-pro",
            openai_client=_FakeOpenAIClient(),
        )

        assert client.context_length == 1024 * 1024
        assert client._context_length == 1024 * 1024


class TestDeepSeekThinkingMode:
    """DeepSeek V4 thinking mode defaults for parse-sensitive agents."""

    def _request(self):
        return ModelRequest(
            model="deepseek-v4-pro",
            messages=[ModelMessage(role="user", content="hi")],
        )

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"})
    def test_v4_pro_disables_thinking_by_default(self):
        client = DeepseekLLMClient(
            model="deepseek-v4-pro",
            openai_client=_FakeOpenAIClient(),
        )

        payload = client._build_request(self._request())

        assert payload["extra_body"]["thinking"] == {"type": "disabled"}

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"})
    def test_v4_pro_can_enable_thinking_explicitly(self):
        client = DeepseekLLMClient(
            model="deepseek-v4-pro",
            thinking_enabled=True,
            openai_client=_FakeOpenAIClient(),
        )

        payload = client._build_request(self._request())

        assert payload["extra_body"]["thinking"] == {"type": "enabled"}

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"})
    def test_disabled_thinking_drops_reasoning_content(self):
        client = DeepseekLLMClient(
            model="deepseek-v4-pro",
            openai_client=_FakeOpenAIClient(),
        )
        output = ModelOutput.build(
            text="Thought: continue\nAction: terminate\nAction Input: {}",
            thinking="private reasoning",
        )
        payload = client._build_request(self._request())

        sanitized = client._drop_thinking_if_disabled(output, payload)

        assert sanitized.has_thinking is False
        assert (
            sanitized.text == "Thought: continue\nAction: terminate\nAction Input: {}"
        )


class _FakeOpenAIClient:
    default_headers = {}
