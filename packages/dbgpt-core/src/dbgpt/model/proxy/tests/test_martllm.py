"""Tests for MartLLM proxy LLM client."""

import os
from unittest.mock import MagicMock, patch

import pytest

from dbgpt.model.proxy.llms.martllm import (
    _MARTLLM_DEFAULT_MODEL,
    MartLLMClient,
    MartLLMDeployModelParameters,
)


@pytest.fixture
def sdk_builder():
    """Replace the SDK client builder, so no HTTP client is built and no
    proxy or Azure settings are read from the process environment."""
    with patch(
        "dbgpt.model.utils.chatgpt_utils._build_openai_client",
        return_value=("open_ai", MagicMock()),
    ) as builder:
        yield builder


class TestMartLLMNewClient:
    """``new_client`` is the path the TOML deployment takes."""

    def test_deploy_params_provider(self):
        assert MartLLMDeployModelParameters.provider == "proxy/martllm"

    @patch.dict(os.environ, {"MARTLLM_API_KEY": "test-key"}, clear=True)
    def test_unset_context_length_keeps_the_128k_default(self, sdk_builder):
        params = MartLLMDeployModelParameters(
            name=_MARTLLM_DEFAULT_MODEL, api_key="test-key"
        )
        assert params.context_length is None
        client = MartLLMClient.new_client(params)
        assert client._context_length == 128 * 1024
        assert client.default_model == _MARTLLM_DEFAULT_MODEL
        sdk_builder.assert_called_once()

    @patch.dict(os.environ, {"MARTLLM_API_KEY": "test-key"}, clear=True)
    def test_configured_context_length_is_passed_through(self, sdk_builder):
        # Below 8192, so the inherited clamp would change it.
        params = MartLLMDeployModelParameters(
            name="deepseek/deepseek-v4-pro", api_key="test-key", context_length=4096
        )
        client = MartLLMClient.new_client(params)
        assert client._context_length == 4096
        assert client.default_model == "deepseek/deepseek-v4-pro"

    @patch.dict(
        os.environ,
        {"MARTLLM_API_KEY": "test-key", "OPENAI_API_TYPE": "azure"},
        clear=True,
    )
    def test_ignores_azure_api_type_from_the_environment(self, sdk_builder):
        params = MartLLMDeployModelParameters(
            name=_MARTLLM_DEFAULT_MODEL, api_key="test-key"
        )
        MartLLMClient.new_client(params)
        init_params = sdk_builder.call_args.kwargs["init_params"]
        assert init_params.api_type == "open_ai"
        assert init_params.api_base == "https://api.martllm.com/v1"
