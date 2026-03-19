"""Tests for MiniMax proxy LLM client."""

import os
from unittest.mock import patch

import pytest

from dbgpt.model.proxy.llms.minimax import (
    _DEFAULT_MODEL,
    MiniMaxDeployModelParameters,
    MiniMaxLLMClient,
)


class TestMiniMaxDefaults:
    """Test MiniMax default model configuration."""

    def test_default_model_is_m27(self):
        assert _DEFAULT_MODEL == "MiniMax-M2.7"

    @patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"})
    def test_client_default_model(self):
        client = MiniMaxLLMClient()
        assert client.default_model == "MiniMax-M2.7"

    @patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"})
    def test_client_custom_model(self):
        client = MiniMaxLLMClient(model="MiniMax-M2.5")
        assert client.default_model == "MiniMax-M2.5"

    def test_deploy_params_provider(self):
        assert MiniMaxDeployModelParameters.provider == "proxy/minimax"


class TestMiniMaxModelList:
    """Test MiniMax model registration."""

    def test_model_list_contains_m27(self):
        # Import triggers registration
        from dbgpt.model.adapter.base import get_model_adapter
        from dbgpt.model.proxy.llms.minimax import MiniMaxLLMClient  # noqa: F811

        adapter = get_model_adapter("proxy/minimax", "MiniMax-M2.7")
        assert adapter is not None

    def test_model_list_contains_m27_highspeed(self):
        from dbgpt.model.adapter.base import get_model_adapter
        from dbgpt.model.proxy.llms.minimax import MiniMaxLLMClient  # noqa: F811

        adapter = get_model_adapter("proxy/minimax", "MiniMax-M2.7-highspeed")
        assert adapter is not None

    def test_model_list_contains_m25(self):
        from dbgpt.model.adapter.base import get_model_adapter
        from dbgpt.model.proxy.llms.minimax import MiniMaxLLMClient  # noqa: F811

        adapter = get_model_adapter("proxy/minimax", "MiniMax-M2.5")
        assert adapter is not None

    def test_model_list_contains_m25_highspeed(self):
        from dbgpt.model.adapter.base import get_model_adapter
        from dbgpt.model.proxy.llms.minimax import MiniMaxLLMClient  # noqa: F811

        adapter = get_model_adapter("proxy/minimax", "MiniMax-M2.5-highspeed")
        assert adapter is not None


class TestMiniMaxTemperatureClamping:
    """Test temperature clamping behavior."""

    @patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"})
    def test_valid_temperature_passthrough(self):
        from dbgpt.core import ModelMessage, ModelRequest

        client = MiniMaxLLMClient()
        request = ModelRequest(
            model="MiniMax-M2.7",
            messages=[ModelMessage(role="user", content="hi")],
            temperature=0.5,
        )
        payload = client._build_request(request)
        assert payload["temperature"] == 0.5

    @patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"})
    def test_high_temperature_clamped(self):
        from dbgpt.core import ModelMessage, ModelRequest

        client = MiniMaxLLMClient()
        request = ModelRequest(
            model="MiniMax-M2.7",
            messages=[ModelMessage(role="user", content="hi")],
            temperature=2.0,
        )
        payload = client._build_request(request)
        assert payload["temperature"] == 1.0
