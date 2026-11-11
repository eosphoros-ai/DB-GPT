"""Tests for DeepSeek proxy LLM client."""

import json
import os
from unittest.mock import patch

import httpx
import pytest
from openai import AsyncOpenAI, BadRequestError

from dbgpt.core import ModelMessage, ModelOutput, ModelRequest
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.model.proxy.llms.deepseek import (
    DeepSeekDeployModelParameters,
    DeepseekLLMClient,
)


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


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "model,tool_choice",
    [
        ("deepseek-v4-flash", "required"),
        (
            "deployment-alias",
            {"type": "function", "function": {"name": "compose_report"}},
        ),
    ],
)
async def test_forced_tools_succeed_on_first_request(stream, model, tool_choice):
    requests = []
    tool_call = {
        "id": "call_report",
        "type": "function",
        "function": {"name": "compose_report", "arguments": "{}"},
    }

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if payload.get("thinking") != {"type": "disabled"}:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Thinking mode does not support this tool_choice"
                    }
                },
            )
        result = {
            "id": "chatcmpl-report",
            "created": 0,
            "model": model,
            "choices": [{"index": 0, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        if stream:
            result["choices"][0]["delta"] = {"tool_calls": [{"index": 0, **tool_call}]}
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=f"data: {json.dumps(result)}\n\ndata: [DONE]\n\n",
            )
        result["choices"][0]["message"] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [tool_call],
        }
        return httpx.Response(200, json=result)

    async with AsyncOpenAI(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        max_retries=0,
    ) as sdk:
        client = DeepseekLLMClient(
            api_key="test-key",
            model=model,
            openai_client=sdk,
        )
        request = ModelRequest(
            model=model,
            messages=[ModelMessage(role="human", content="Compose the report.")],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "compose_report",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            tool_choice=tool_choice,
        )
        if stream:
            outputs = [output async for output in client.generate_stream(request)]
            output = outputs[-1]
        else:
            output = await client.generate(request)
        assert output.error_code == 0, output.text
        assert output.tool_calls == [tool_call]
        assert output.finish_reason == "tool_calls"
        assert output.usage["total_tokens"] == 15
    assert len(requests) == 1
    assert requests[0]["tool_choice"] == tool_choice
    assert requests[0]["tools"] == request.tools


@pytest.mark.parametrize(
    "model,thinking_enabled,expected",
    [
        ("deepseek-v4-flash", None, None),
        ("deployment-alias", None, None),
        ("deepseek-v4-pro", None, {"type": "disabled"}),
        ("deepseek-v4-pro", True, {"type": "enabled"}),
        ("deepseek-chat", True, {"type": "enabled"}),
        ("deepseek-reasoner", False, {"type": "disabled"}),
    ],
)
def test_third_party_forced_tools_preserve_existing_policy(
    model, thinking_enabled, expected
):
    client = DeepseekLLMClient(
        api_key="test-key",
        model=model,
        thinking_enabled=thinking_enabled,
        openai_client=_FakeOpenAIClient("https://compatible.example/v1"),
    )
    payload = client._build_request(
        ModelRequest(model=model, messages=[], tool_choice="required")
    )
    assert (payload.get("extra_body") or {}).get("thinking") == expected


@pytest.mark.parametrize(
    "extra_body", [None, {"thinking": {"type": "enabled"}, "custom": True}]
)
def test_forced_tools_do_not_mutate_shared_defaults_or_ordinary_requests(extra_body):
    from copy import deepcopy

    original = deepcopy(extra_body)
    client = DeepseekLLMClient(
        api_key="test-key",
        model="deployment-alias",
        openai_kwargs={"extra_body": extra_body} if extra_body else None,
        openai_client=_FakeOpenAIClient(),
    )
    forced = client._build_request(
        ModelRequest(model="deployment-alias", messages=[], tool_choice="required")
    )
    assert forced["extra_body"] == {
        **(original or {}),
        "thinking": {"type": "disabled"},
    }
    for tool_choice in (None, "auto", "none"):
        ordinary = client._build_request(
            ModelRequest(model="deployment-alias", messages=[], tool_choice=tool_choice)
        )
        assert ordinary.get("extra_body") == original
    assert extra_body == original


@pytest.mark.parametrize("thinking_enabled", [None, True, False])
def test_official_forced_tools_do_not_change_ordinary_thinking_policy(thinking_enabled):
    client = DeepseekLLMClient(
        api_key="test-key",
        model="deepseek-v4-flash",
        thinking_enabled=thinking_enabled,
        openai_client=_FakeOpenAIClient(),
    )
    forced = client._build_request(
        ModelRequest(model="deepseek-v4-flash", messages=[], tool_choice="required")
    )
    assert forced["extra_body"]["thinking"] == {"type": "disabled"}
    expected = (
        None
        if thinking_enabled is None
        else {"type": "enabled" if thinking_enabled else "disabled"}
    )
    for tool_choice in (None, "auto", "none"):
        payload = client._build_request(
            ModelRequest(
                model="deepseek-v4-flash", messages=[], tool_choice=tool_choice
            )
        )
        assert (payload.get("extra_body") or {}).get("thinking") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_class,actual_base,expected",
    [
        (DeepseekLLMClient, "https://api.deepseek.com/v1", {"type": "disabled"}),
        (DeepseekLLMClient, "https://compatible.example/v1", None),
        (DeepseekLLMClient, "https://api.deepseek.com.compatible.example/v1", None),
        (OpenAILLMClient, "https://api.deepseek.com/v1", None),
    ],
)
async def test_automatic_policy_uses_actual_endpoint_and_provider(
    client_class, actual_base, expected
):
    async with AsyncOpenAI(api_key="test-key", base_url=actual_base) as sdk:
        client = client_class(
            api_key="test-key",
            api_base="https://api.deepseek.com/v1",
            model="deepseek-v4-flash",
            openai_client=sdk,
        )
        payload = client._build_request(
            ModelRequest(model="deepseek-v4-flash", messages=[], tool_choice="required")
        )
    assert (payload.get("extra_body") or {}).get("thinking") == expected


def test_ui_deployment_parameters_need_no_extra_option_for_forced_tools():
    params = DeepSeekDeployModelParameters(
        name="deployment-alias",
        provider="proxy/deepseek",
        api_key="test-key",
        api_base="https://api.deepseek.com/v1",
    )
    with patch(
        "dbgpt.model.utils.chatgpt_utils._build_openai_client",
        return_value=("openai", _FakeOpenAIClient()),
    ):
        client = DeepseekLLMClient.new_client(params)
    payload = client._build_request(
        ModelRequest(model="deployment-alias", messages=[], tool_choice="required")
    )
    assert payload["extra_body"]["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "api_base,message,expected_thinking",
    [
        (
            "https://compatible.example/v1",
            "Thinking mode does not support this tool_choice",
            "enabled",
        ),
        ("https://api.deepseek.com/v1", "Invalid tool schema", "disabled"),
    ],
)
async def test_provider_errors_keep_original_behavior_without_retry(
    stream, api_base, message, expected_thinking
):
    requests = []

    def reject(request):
        requests.append(json.loads(request.content))
        return httpx.Response(400, json={"error": {"message": message}})

    async with AsyncOpenAI(
        api_key="test-key",
        base_url=api_base,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(reject)),
        max_retries=0,
    ) as sdk:
        client = DeepseekLLMClient(
            api_key="test-key",
            model="deepseek-v4-pro",
            thinking_enabled=True,
            openai_client=sdk,
        )
        request = ModelRequest(
            model="deepseek-v4-pro", messages=[], tool_choice="required"
        )
        if stream:
            with pytest.raises(BadRequestError, match=message):
                async for _ in client.generate_stream(request):
                    pass
        else:
            output = await client.generate(request)
            assert output.error_code == 1 and message in output.text
    assert len(requests) == 1
    assert requests[0]["thinking"] == {"type": expected_thinking}


class _FakeOpenAIClient:
    default_headers = {}

    def __init__(self, base_url="https://api.deepseek.com/v1"):
        self.base_url = httpx.URL(base_url)
