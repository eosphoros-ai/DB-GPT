"""Tests for UberLLM proxy LLM client."""

import os
from unittest.mock import patch

from dbgpt.model.proxy.llms.uberllm import (
    _UBERLLM_DEFAULT_MODEL,
    UberLLMClient,
    UberLLMDeployModelParameters,
)


class TestUberLLMNewClient:
    """``new_client`` is the path the TOML deployment takes."""

    def test_deploy_params_provider(self):
        assert UberLLMDeployModelParameters.provider == "proxy/uberllm"

    @patch.dict(os.environ, {"UBERLLM_API_KEY": "test-key"})
    def test_unset_context_length_keeps_the_128k_default(self):
        params = UberLLMDeployModelParameters(
            name=_UBERLLM_DEFAULT_MODEL, api_key="test-key"
        )
        assert params.context_length is None
        client = UberLLMClient.new_client(params)
        assert client._context_length == 128 * 1024
        assert client.default_model == _UBERLLM_DEFAULT_MODEL

    @patch.dict(os.environ, {"UBERLLM_API_KEY": "test-key"})
    def test_configured_context_length_is_passed_through(self):
        params = UberLLMDeployModelParameters(
            name="google/gemini-2.5-pro", api_key="test-key", context_length=1_000_000
        )
        client = UberLLMClient.new_client(params)
        assert client._context_length == 1_000_000
        assert client.default_model == "google/gemini-2.5-pro"
