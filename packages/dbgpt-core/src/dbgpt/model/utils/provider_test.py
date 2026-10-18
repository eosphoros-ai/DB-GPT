"""Real connectivity test for model providers.

Verifies a provider's credentials by actually calling its model-list endpoint
(e.g. ``GET {api_base}/models`` for OpenAI-compatible providers), so a
successful "connect" means the key really works.
"""

import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{env:([A-Za-z0-9_]+)(?::-(.*?))?\}")

_DEFAULT_TIMEOUT = 15.0

# Anthropic is not OpenAI-compatible: different base url / headers / path.
_ANTHROPIC_DEFAULT_BASE = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"

_GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com"

_OLLAMA_DEFAULT_BASE = "http://localhost:11434"

# Providers that work without any API key (e.g. a local Ollama server).
NO_API_KEY_REQUIRED_PROVIDERS = frozenset({"proxy/ollama"})

# Providers whose HTTP API has no model-list endpoint to probe (or no fixed
# base url), so "connect" cannot verify credentials and is accepted as-is.
_PROBE_SKIPPED_PROVIDERS = frozenset({"proxy/spark", "proxy/litellm"})

# Baidu Qianfan (wenxin) uses an AK/SK pair packed as "AK:SK"; verify it by
# exchanging them for an OAuth access token.
_WENXIN_OAUTH_URL = "https://aip.baidubce.com/oauth/2.0/token"

# GitHub Copilot accepts no static key; verify the PAT by exchanging it for a
# short-lived Copilot API token (same endpoint the client uses at runtime).
_GITHUB_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"


def _resolve_env_template(value: str) -> str:
    """Resolve ``${env:VAR:-default}`` placeholders against the environment."""

    def _sub(match: re.Match) -> str:
        var, default = match.group(1), match.group(2)
        return os.environ.get(var) or (default or "")

    return _ENV_PATTERN.sub(_sub, value)


def _default_api_base(provider: str) -> Optional[str]:
    """Resolve the provider's default api_base from its deploy parameters."""
    try:
        from dbgpt.model.utils.llm_utils import list_supported_models

        for model in list_supported_models():
            if model.provider != provider:
                continue
            for param in model.params or []:
                if param.param_name == "api_base" and param.default_value:
                    resolved = _resolve_env_template(str(param.default_value))
                    if resolved:
                        return resolved
    except Exception as e:
        logger.warning(f"resolve default api_base for {provider} failed: {e}")
    return None


def _build_test_request(provider: str, api_key: str, api_base: Optional[str]):
    """Build (url, headers) for the provider's model-list probe."""
    if provider == "proxy/claude":
        base = (api_base or _ANTHROPIC_DEFAULT_BASE).rstrip("/")
        return f"{base}/v1/models", {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
    if provider == "proxy/gemini":
        base = (api_base or _GEMINI_DEFAULT_BASE).rstrip("/")
        return f"{base}/v1beta/models?key={api_key}", {}
    if provider == "proxy/ollama":
        base = (api_base or _OLLAMA_DEFAULT_BASE).rstrip("/")
        # Native list endpoint; requires no auth and exists on every version.
        return f"{base}/api/tags", {}
    if provider == "proxy/github_copilot":
        # Copilot has no model-list endpoint; verify the PAT by exchanging it
        # for a short-lived Copilot token.
        return _GITHUB_TOKEN_URL, {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
    if provider == "proxy/wenxin":
        ak, _, sk = (api_key or "").partition(":")
        if not ak or not sk:
            return "", {}
        return (
            f"{_WENXIN_OAUTH_URL}"
            f"?grant_type=client_credentials&client_id={ak}&client_secret={sk}",
            {},
        )
    # OpenAI-compatible providers (including custom/xxx virtual providers)
    base = (api_base or _default_api_base(provider) or "").rstrip("/")
    return f"{base}/models", {"Authorization": f"Bearer {api_key}"}


async def test_provider_connection(
    provider: str,
    api_key: Optional[str],
    api_base: Optional[str] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> Tuple[bool, str]:
    """Test whether the provider is reachable with the given credentials.

    Returns:
        (ok, message): ok is True when the provider accepted the credentials;
        message is a human-readable failure reason otherwise.
    """
    import httpx

    if provider in NO_API_KEY_REQUIRED_PROVIDERS:
        api_key = api_key or None
    elif not api_key:
        return False, "api_key is required"

    if provider in _PROBE_SKIPPED_PROVIDERS:
        return True, "credentials not verified for this provider"

    effective_provider = "proxy/openai" if provider.startswith("custom/") else provider
    url, headers = _build_test_request(effective_provider, api_key or "", api_base)
    if not url or url.startswith("/"):
        if effective_provider == "proxy/wenxin":
            return False, "wenxin api_key must be in 'AK:SK' format"
        return False, f"cannot resolve api base url for provider {provider}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
    except Exception as e:
        detail = str(e) or repr(e)
        return False, f"network error: {detail}"
    if resp.status_code == 200:
        if effective_provider == "proxy/wenxin":
            try:
                if "access_token" in resp.json():
                    return True, ""
            except ValueError:
                pass
            return False, "invalid wenxin ak/sk"
        if effective_provider == "proxy/github_copilot":
            try:
                if resp.json().get("token"):
                    return True, ""
            except ValueError:
                pass
            return False, "invalid github pat or no active copilot subscription"
        return True, ""
    if resp.status_code in (401, 403):
        return False, "invalid api key"
    if resp.status_code == 404 and effective_provider == "proxy/github_copilot":
        # GitHub rejects Personal Access Tokens for Copilot with 404; only
        # OAuth tokens from the device flow are accepted.
        return False, (
            "GitHub does not accept Personal Access Tokens for Copilot; "
            "connect via GitHub sign-in (OAuth device flow) instead"
        )
    return False, f"provider returned HTTP {resp.status_code}"
