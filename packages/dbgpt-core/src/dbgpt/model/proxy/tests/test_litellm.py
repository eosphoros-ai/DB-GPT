"""Tests for LiteLLM proxy LLM client."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

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
        payload = client._build_request(
            self._request(model="groq/llama-3.3-70b-versatile")
        )
        assert payload["model"] == "groq/llama-3.3-70b-versatile"

    def test_api_credentials_passed_when_provided(self):
        client = LiteLLMClient(api_key="sk-test", api_base="https://example.invalid/v1")
        payload = client._build_request(self._request())
        assert payload["api_key"] == "sk-test"
        assert payload["api_base"] == "https://example.invalid/v1"

    def test_api_credentials_omitted_when_unset(self):
        client = LiteLLMClient()
        payload = client._build_request(self._request())
        assert "api_key" not in payload
        assert "api_base" not in payload

    def test_tools_passthrough(self):
        tools = [
            {
                "type": "function",
                "function": {"name": "get_weather", "parameters": {}},
            }
        ]
        client = LiteLLMClient(litellm_kwargs={"tools": tools, "tool_choice": "auto"})
        payload = client._build_request(self._request())
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"


# ---------------------------------------------------------------------------
# Mocked generate() + generate_stream() — exercises the LiteLLM adapter logic
# across the response shapes LiteLLM emits for different upstream providers.
# We patch litellm.acompletion so the tests don't need network access.
# ---------------------------------------------------------------------------


def _make_response(content, usage=None, reasoning_content=None):
    """Mock the non-streaming litellm.acompletion return value (OpenAI shape)."""
    message = SimpleNamespace(content=content)
    if reasoning_content is not None:
        message.reasoning_content = reasoning_content
    choice = SimpleNamespace(message=message)
    usage_obj = None
    if usage is not None:
        usage_obj = SimpleNamespace(model_dump=lambda u=usage: u)
    return SimpleNamespace(choices=[choice], usage=usage_obj)


def _make_chunk(content=None, reasoning=None, usage=None, finish=False):
    """Mock a single streaming chunk."""
    delta = SimpleNamespace(content=content)
    if reasoning is not None:
        delta.reasoning_content = reasoning
    choices = []
    if not (usage is not None and content is None and reasoning is None and not finish):
        # Non-usage-only chunks always include a choice.
        choices = [SimpleNamespace(delta=delta)]
    chunk_usage = None
    if usage is not None:
        chunk_usage = SimpleNamespace(model_dump=lambda u=usage: u)
    return SimpleNamespace(choices=choices, usage=chunk_usage)


def _usage_only_chunk(usage):
    """Mock the OpenAI stream_options=include_usage trailing chunk: empty
    choices, usage attached."""
    chunk_usage = SimpleNamespace(model_dump=lambda u=usage: u)
    return SimpleNamespace(choices=[], usage=chunk_usage)


async def _async_iter(chunks):
    for c in chunks:
        yield c


class TestLiteLLMGenerate:
    """generate() — non-streaming response handling and error path."""

    def _request(self, **overrides):
        from dbgpt.core import ModelMessage, ModelRequest
        from dbgpt.core.interface.message import ModelMessageRoleType

        defaults = dict(
            model="anthropic/claude-3-5-sonnet-20241022",
            messages=[
                ModelMessage(role=ModelMessageRoleType.HUMAN, content="hi"),
            ],
        )
        defaults.update(overrides)
        return ModelRequest(**defaults)

    def test_generate_returns_text_and_usage(self):
        client = LiteLLMClient()
        usage = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}

        async def run():
            with patch(
                "litellm.acompletion",
                return_value=_make_response("4", usage=usage),
            ):
                return await client.generate(self._request())

        out = asyncio.run(run())
        assert out.error_code == 0
        assert out.text == "4"
        assert out.usage == usage

    def test_generate_propagates_reasoning_content(self):
        client = LiteLLMClient()

        async def run():
            with patch(
                "litellm.acompletion",
                return_value=_make_response(
                    "answer", usage=None, reasoning_content="thought"
                ),
            ):
                return await client.generate(self._request())

        out = asyncio.run(run())
        # ModelOutput.build packs reasoning into a structured content list with
        # MediaContent entries of type="thinking" and type="text".
        types_to_text = {mc.type: mc.object.data for mc in (out.content or [])}
        assert types_to_text.get("thinking") == "thought"
        assert types_to_text.get("text") == "answer"

    def test_generate_error_returns_error_code_one(self):
        client = LiteLLMClient()

        async def run():
            with patch(
                "litellm.acompletion",
                side_effect=RuntimeError("boom"),
            ):
                return await client.generate(self._request())

        out = asyncio.run(run())
        assert out.error_code == 1
        assert "boom" in out.text


class TestLiteLLMGenerateStream:
    """generate_stream() — provider-shape coverage without live keys."""

    def _request(self, **overrides):
        from dbgpt.core import ModelMessage, ModelRequest
        from dbgpt.core.interface.message import ModelMessageRoleType

        defaults = dict(
            model="anthropic/claude-3-5-sonnet-20241022",
            messages=[
                ModelMessage(role=ModelMessageRoleType.HUMAN, content="hi"),
            ],
        )
        defaults.update(overrides)
        return ModelRequest(**defaults)

    def _collect(self, client, chunks):
        async def run():
            with patch(
                "litellm.acompletion",
                return_value=_async_iter(chunks),
            ):
                outputs = []
                async for o in client.generate_stream(self._request()):
                    outputs.append(o)
                return outputs

        return asyncio.run(run())

    def test_openai_style_separate_usage_chunk(self):
        """Azure / OpenAI with stream_options=include_usage: usage arrives in a
        trailing choices=[] chunk; finish-only intermediate chunk should not
        cause duplicate frames."""
        client = LiteLLMClient()
        usage = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        outputs = self._collect(
            client,
            [
                _make_chunk(content="1"),
                _make_chunk(content=", 2"),
                _make_chunk(content=", 3"),
                _make_chunk(content="", finish=True),  # finish-only chunk
                _usage_only_chunk(usage),
            ],
        )
        texts = [o.text for o in outputs]
        # No duplicate text frames at the tail.
        assert texts == ["1", "1, 2", "1, 2, 3"]
        assert outputs[-1].error_code == 0

    def test_anthropic_style_inline_usage(self):
        """Anthropic via LiteLLM attaches usage onto the last content chunk."""
        client = LiteLLMClient()
        usage = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        outputs = self._collect(
            client,
            [
                _make_chunk(content="1"),
                _make_chunk(content=", 2"),
                _make_chunk(content=", 3", usage=usage),
            ],
        )
        texts = [o.text for o in outputs]
        # Final yield contains both the full text and usage. No duplicate.
        assert texts == ["1", "1, 2", "1, 2, 3"]
        assert outputs[-1].usage == usage

    def test_no_duplicate_on_finish_only_chunk(self):
        """A finish chunk with no new content/reasoning must not emit a frame."""
        client = LiteLLMClient()
        outputs = self._collect(
            client,
            [
                _make_chunk(content="hi"),
                # finish chunk: choices present but delta.content is "" / None
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
                    usage=None,
                ),
            ],
        )
        assert [o.text for o in outputs] == ["hi"]

    def test_error_yields_error_code_one(self):
        client = LiteLLMClient()

        async def run():
            with patch("litellm.acompletion", side_effect=RuntimeError("net dead")):
                outs = []
                async for o in client.generate_stream(self._request()):
                    outs.append(o)
                return outs

        outputs = asyncio.run(run())
        assert len(outputs) == 1
        assert outputs[0].error_code == 1
        assert "net dead" in outputs[0].text


class TestLiteLLMNewClient:
    """new_client() — DB-GPT's actual entry point when loading a deploy config."""

    def test_new_client_constructs_with_params(self):
        params = LiteLLMDeployModelParameters(
            name="anthropic/claude-3-5-sonnet-20241022",
            provider="proxy/litellm",
        )
        client = LiteLLMClient.new_client(params)
        assert isinstance(client, LiteLLMClient)
        assert client.default_model == "anthropic/claude-3-5-sonnet-20241022"
        assert client._model_alias == "anthropic/claude-3-5-sonnet-20241022"

    def test_new_client_preserves_drop_params_default(self):
        params = LiteLLMDeployModelParameters(
            name="groq/llama-3.3-70b-versatile",
            provider="proxy/litellm",
        )
        client = LiteLLMClient.new_client(params)
        assert client._litellm_kwargs.get("drop_params") is True


class TestLiteLLMImportGuard:
    def test_import_error_message_mentions_pin(self):
        # Force-fail the litellm import inside __init__ to verify the user-
        # facing error names the supported version range.
        import sys

        saved = sys.modules.pop("litellm", None)
        sys.modules["litellm"] = None  # type: ignore[assignment]
        try:
            with pytest.raises(ValueError, match=r"litellm>=1\.60"):
                LiteLLMClient()
        finally:
            if saved is not None:
                sys.modules["litellm"] = saved
            else:
                sys.modules.pop("litellm", None)
