import pytest

from dbgpt.model.utils.provider_test import (
    _PROBE_SKIPPED_PROVIDERS,
    NO_API_KEY_REQUIRED_PROVIDERS,
    _build_test_request,
)
from dbgpt.model.utils.provider_test import (
    test_provider_connection as _test_connection,
)


@pytest.mark.parametrize(
    "provider,api_key,api_base,expected_url_prefix",
    [
        # Ollama probes the native /api/tags endpoint without auth.
        ("proxy/ollama", "", None, "http://localhost:11434/api/tags"),
        (
            "proxy/ollama",
            "",
            "http://my-ollama:11434/",
            "http://my-ollama:11434/api/tags",
        ),
        # Claude probes the Anthropic messages endpoint with versioned headers.
        (
            "proxy/claude",
            "sk-ant",
            None,
            "https://api.anthropic.com/v1/models",
        ),
        # Gemini uses the key as a query parameter.
        (
            "proxy/gemini",
            "g-key",
            None,
            "https://generativelanguage.googleapis.com/v1beta/models?key=g-key",
        ),
        # Wenxin exchanges AK:SK for an OAuth token.
        (
            "proxy/wenxin",
            "my-ak:my-sk",
            None,
            "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials"
            "&client_id=my-ak&client_secret=my-sk",
        ),
        # Copilot verifies the PAT through the token exchange endpoint.
        (
            "proxy/github_copilot",
            "ghp_x",
            None,
            "https://api.github.com/copilot_internal/v2/token",
        ),
    ],
)
def test_build_test_request(provider, api_key, api_base, expected_url_prefix):
    url, headers = _build_test_request(provider, api_key, api_base)
    assert url == expected_url_prefix
    if provider == "proxy/ollama":
        assert headers == {}
    if provider == "proxy/claude":
        assert headers["x-api-key"] == "sk-ant"


def test_build_test_request_openai_compat():
    url, headers = _build_test_request(
        "proxy/openai", "sk-x", "https://api.example.com/v1/"
    )
    assert url == "https://api.example.com/v1/models"
    assert headers == {"Authorization": "Bearer sk-x"}


def test_no_api_key_required_contains_ollama():
    assert "proxy/ollama" in NO_API_KEY_REQUIRED_PROVIDERS


@pytest.mark.asyncio
async def test_skipped_providers_pass_without_probe():
    for provider in _PROBE_SKIPPED_PROVIDERS:
        ok, msg = await _test_connection(provider, "whatever-key")
        assert ok is True


@pytest.mark.asyncio
async def test_missing_api_key_rejected():
    ok, msg = await _test_connection("proxy/openai", None)
    assert ok is False
    assert "api_key" in msg


@pytest.mark.asyncio
async def test_ollama_allows_empty_key():
    """Empty key is accepted for ollama (goes on to probe the local server)."""
    ok, msg = await _test_connection("proxy/ollama", None, timeout=2.0)
    # No local ollama in CI: expect a network failure, NOT an api_key rejection.
    assert "api_key" not in msg
