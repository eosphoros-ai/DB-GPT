"""Tests for LiteLLM proxy LLM client."""

from dbgpt.model.proxy.llms.litellm import (
    _DEFAULT_MODEL,
    LiteLLMClient,
    LiteLLMDeployModelParameters,
)


class TestLiteLLMDefaults:
    """LiteLLM default model + parameter configuration."""

    def test_default_model_constant(self):
        assert _DEFAULT_MODEL == "openai/gpt-4o-mini"

    def test_client_default_model(self):
        client = LiteLLMClient()
        assert client.default_model == "openai/gpt-4o-mini"

    def test_client_custom_model(self):
        client = LiteLLMClient(model="anthropic/claude-3-5-sonnet-20241022")
        assert client.default_model == "anthropic/claude-3-5-sonnet-20241022"

    def test_model_alias_falls_back_to_model(self):
        client = LiteLLMClient(model="vertex_ai/gemini-1.5-pro")
        assert client._model_alias == "vertex_ai/gemini-1.5-pro"

    def test_deploy_params_provider(self):
        assert LiteLLMDeployModelParameters.provider == "proxy/litellm"


class TestLiteLLMModelRegistration:
    """LiteLLM provider/model adapter resolution."""

    def test_openai_routed_via_litellm_resolves(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter("proxy/litellm", "openai/gpt-4o")
        assert adapter is not None

    def test_anthropic_routed_via_litellm_resolves(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter(
            "proxy/litellm", "anthropic/claude-3-5-sonnet-20241022"
        )
        assert adapter is not None

    def test_bedrock_routed_via_litellm_resolves(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter(
            "proxy/litellm", "bedrock/anthropic.claude-3-haiku-20240307-v1:0"
        )
        assert adapter is not None

    def test_azure_routed_via_litellm_resolves(self):
        from dbgpt.model.adapter.base import get_model_adapter

        adapter = get_model_adapter("proxy/litellm", "azure/gpt-4o")
        assert adapter is not None


class TestLiteLLMBuildRequest:
    """_build_request payload assembly."""

    def _request(self, **overrides):
        from dbgpt.core import ModelMessage, ModelRequest

        defaults = dict(
            model="anthropic/claude-3-5-sonnet-20241022",
            messages=[ModelMessage(role="user", content="hi")],
        )
        defaults.update(overrides)
        return ModelRequest(**defaults)

    def test_drop_params_defaulted_on(self):
        client = LiteLLMClient()
        payload = client._build_request(self._request())
        assert payload["drop_params"] is True

    def test_drop_params_can_be_disabled(self):
        client = LiteLLMClient(litellm_kwargs={"drop_params": False})
        payload = client._build_request(self._request())
        assert payload["drop_params"] is False

    def test_user_litellm_kwargs_merged(self):
        client = LiteLLMClient(litellm_kwargs={"num_retries": 3})
        payload = client._build_request(self._request())
        assert payload["num_retries"] == 3
        # And drop_params default is preserved.
        assert payload["drop_params"] is True

    def test_temperature_and_max_tokens_forwarded(self):
        client = LiteLLMClient()
        payload = client._build_request(
            self._request(temperature=0.3, max_new_tokens=512)
        )
        assert payload["temperature"] == 0.3
        assert payload["max_tokens"] == 512

    def test_stream_options_set_on_streaming(self):
        client = LiteLLMClient()
        payload = client._build_request(self._request(), stream=True)
        assert payload["stream"] is True
        assert payload["stream_options"] == {"include_usage": True}

    def test_stream_options_absent_on_non_stream(self):
        client = LiteLLMClient()
        payload = client._build_request(self._request())
        assert payload["stream"] is False
        assert "stream_options" not in payload

    def test_model_resolution_uses_request_model_first(self):
        client = LiteLLMClient(model="openai/gpt-4o-mini")
        payload = client._build_request(self._request(model="groq/llama-3.3-70b-versatile"))
        assert payload["model"] == "groq/llama-3.3-70b-versatile"

    def test_api_credentials_passed_when_provided(self):
        client = LiteLLMClient(
            api_key="sk-test", api_base="https://example.invalid/v1"
        )
        payload = client._build_request(self._request())
        assert payload["api_key"] == "sk-test"
        assert payload["api_base"] == "https://example.invalid/v1"

    def test_api_credentials_omitted_when_unset(self):
        client = LiteLLMClient()
        payload = client._build_request(self._request())
        assert "api_key" not in payload
        assert "api_base" not in payload
