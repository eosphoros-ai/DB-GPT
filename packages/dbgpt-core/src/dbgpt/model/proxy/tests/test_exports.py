"""Public proxy client imports remain available through lazy exports."""

import importlib

import pytest

from dbgpt.model import proxy


@pytest.mark.parametrize(
    "name,module",
    [
        ("GithubCopilotLLMClient", "github_copilot"),
        ("GroqLLMClient", "groq"),
        ("MistralLLMClient", "mistral"),
        ("VercelAIGatewayLLMClient", "vercel"),
        ("XaiLLMClient", "xai"),
        ("ApiRouteLLMClient", "api_route"),
    ],
)
def test_public_client_export(name, module):
    exported = getattr(proxy, name)
    concrete_module = importlib.import_module(f"dbgpt.model.proxy.llms.{module}")
    assert exported is getattr(concrete_module, name)
    assert name in proxy.__all__


def test_unknown_export_raises_attribute_error():
    with pytest.raises(AttributeError, match="UnknownProxyClient"):
        getattr(proxy, "UnknownProxyClient")
