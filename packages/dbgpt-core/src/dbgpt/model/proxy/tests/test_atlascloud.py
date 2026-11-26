"""Tests for Atlas Cloud proxy LLM client."""

import os
from unittest.mock import patch

import pytest

from dbgpt.model.proxy.llms.atlascloud import (
    AtlasCloudDeployModelParameters,
    AtlasCloudLLMClient,
)


class _FakeOpenAIClient:
    default_headers = {}


def _params(**kwargs) -> AtlasCloudDeployModelParameters:
    defaults = dict(
        name="deepseek-ai/deepseek-v4-pro",
        provider="proxy/atlascloud",
        api_key="test-key",
    )
    defaults.update(kwargs)
    return AtlasCloudDeployModelParameters(**defaults)


class TestAtlasCloudRegistration:
    def test_adapter_resolves_registered_model(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter("proxy/atlascloud", "deepseek-ai/deepseek-v4-pro")
        assert adapter is not None
        metadata = {m: meta for meta in adapter.supported_models() for m in meta.model}
        assert metadata["deepseek-ai/deepseek-v4-pro"].context_length == 1_048_576


class TestAtlasCloudClient:
    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ATLASCLOUD_API_KEY", None)
            with pytest.raises(ValueError, match="ATLASCLOUD_API_KEY"):
                AtlasCloudLLMClient(openai_client=_FakeOpenAIClient())

    def test_env_key_and_default_context_length(self, monkeypatch):
        monkeypatch.setenv("ATLASCLOUD_API_KEY", "env-key")
        monkeypatch.delenv("ATLASCLOUD_API_BASE", raising=False)
        client = AtlasCloudLLMClient(openai_client=_FakeOpenAIClient())

        assert client._init_params.api_key == "env-key"
        assert client._init_params.api_base == "https://api.atlascloud.ai/v1"
        assert client.default_model == "deepseek-ai/DeepSeek-V3.1-Terminus"
        assert client.context_length == 128 * 1024

    @pytest.mark.parametrize(
        "api_base", ["http://api.atlascloud.ai/v1", "ftp://api.atlascloud.ai/v1", ""]
    )
    def test_plaintext_or_invalid_api_base_is_rejected(self, monkeypatch, api_base):
        monkeypatch.setenv("ATLASCLOUD_API_KEY", "env-key")
        monkeypatch.setenv("ATLASCLOUD_API_BASE", api_base or "relative/path")
        with pytest.raises(ValueError, match="must use https"):
            AtlasCloudLLMClient(openai_client=_FakeOpenAIClient())
        monkeypatch.delenv("ATLASCLOUD_API_BASE")
        with pytest.raises(ValueError, match="must use https"):
            AtlasCloudLLMClient(
                api_base=api_base or "relative/path",
                openai_client=_FakeOpenAIClient(),
            )

    def test_loopback_http_and_https_bases_are_allowed(self, monkeypatch):
        monkeypatch.setenv("ATLASCLOUD_API_KEY", "env-key")
        monkeypatch.delenv("ATLASCLOUD_API_BASE", raising=False)
        for base in ("http://localhost:8000/v1", "https://gateway.example.com/v1"):
            client = AtlasCloudLLMClient(
                api_base=base, openai_client=_FakeOpenAIClient()
            )
            assert client._init_params.api_base == base

    def test_new_client_keeps_default_context_length_when_unset(self):
        # OpenAILLMClient.new_client would floor this to 8192.
        with patch(
            "dbgpt.model.utils.chatgpt_utils._build_openai_client",
            return_value=("openai", _FakeOpenAIClient()),
        ):
            client = AtlasCloudLLMClient.new_client(_params())

        assert client.context_length == 128 * 1024
        assert client.default_model == "deepseek-ai/deepseek-v4-pro"

    def test_new_client_respects_explicit_context_length(self):
        with patch(
            "dbgpt.model.utils.chatgpt_utils._build_openai_client",
            return_value=("openai", _FakeOpenAIClient()),
        ):
            client = AtlasCloudLLMClient.new_client(_params(context_length=32768))

        assert client.context_length == 32768
