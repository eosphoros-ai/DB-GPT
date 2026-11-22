"""Tests for MartLLM proxy LLM client."""

import os
from unittest.mock import patch

from dbgpt.model.proxy.llms.martllm import (
    _MARTLLM_DEFAULT_MODEL,
    MartLLMClient,
    MartLLMDeployModelParameters,
)


class TestMartLLMNewClient:
    """``new_client`` is the path the TOML deployment takes."""

    def test_deploy_params_provider(self):
        assert MartLLMDeployModelParameters.provider == "proxy/martllm"

    @patch.dict(os.environ, {"MARTLLM_API_KEY": "test-key"})
    def test_unset_context_length_keeps_the_128k_default(self):
        params = MartLLMDeployModelParameters(
            name=_MARTLLM_DEFAULT_MODEL, api_key="test-key"
        )
        assert params.context_length is None
        client = MartLLMClient.new_client(params)
        assert client._context_length == 128 * 1024
        assert client.default_model == _MARTLLM_DEFAULT_MODEL

    @patch.dict(os.environ, {"MARTLLM_API_KEY": "test-key"})
    def test_configured_context_length_is_passed_through(self):
        params = MartLLMDeployModelParameters(
            name="google/gemini-2.5-pro", api_key="test-key", context_length=1_000_000
        )
        client = MartLLMClient.new_client(params)
        assert client._context_length == 1_000_000
        assert client.default_model == "google/gemini-2.5-pro"
