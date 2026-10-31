"""Tests for Runcrate proxy LLM client."""

import os
from unittest.mock import patch

import pytest

from dbgpt.model.proxy.llms.runcrate import (
    _RUNCRATE_DEFAULT_API_BASE,
    _RUNCRATE_DEFAULT_MODEL,
    RuncrateDeployModelParameters,
    RuncrateLLMClient,
)


class TestRuncrateDefaults:
    """Test Runcrate default configuration."""

    def test_default_model(self):
        assert _RUNCRATE_DEFAULT_MODEL == "deepseek-ai/DeepSeek-V4.1-Flash"

    def test_deploy_params_provider(self):
        assert RuncrateDeployModelParameters.provider == "proxy/runcrate"

    @patch.dict(os.environ, {"RUNCRATE_API_KEY": "test-key"}, clear=False)
    def test_client_defaults(self):
        os.environ.pop("RUNCRATE_API_BASE", None)
        client = RuncrateLLMClient()
        assert client.default_model == _RUNCRATE_DEFAULT_MODEL
        assert str(client.client.base_url).rstrip("/") == _RUNCRATE_DEFAULT_API_BASE

    @patch.dict(os.environ, {"RUNCRATE_API_KEY": "test-key"})
    def test_client_custom_model(self):
        client = RuncrateLLMClient(model="zai-org/GLM-5.3")
        assert client.default_model == "zai-org/GLM-5.3"

    @patch.dict(
        os.environ,
        {"RUNCRATE_API_KEY": "test-key", "RUNCRATE_API_BASE": "http://localhost:9/v1"},
    )
    def test_client_api_base_from_env(self):
        client = RuncrateLLMClient()
        assert str(client.client.base_url).rstrip("/") == "http://localhost:9/v1"

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="RUNCRATE_API_KEY"):
            RuncrateLLMClient()


class TestRuncrateModelList:
    """Test Runcrate model registration."""

    @pytest.mark.parametrize(
        "model",
        [
            "deepseek-ai/DeepSeek-V4.1-Flash",
            "zai-org/GLM-5.3",
            "zai-org/GLM-5.3-Flash",
            "Qwen/Qwen3.8-Flash",
            "moonshotai/Kimi-K2.6",
            "openai/gpt-oss-120b",
        ],
    )
    def test_registered_models(self, model):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter("proxy/runcrate", model)
        assert adapter is not None

    def test_models_dev_catalog_has_runcrate(self):
        from dbgpt.model.utils.models_dev import get_models_dev_models

        models = [m["model"] for m in get_models_dev_models("proxy/runcrate")]
        assert _RUNCRATE_DEFAULT_MODEL in models
