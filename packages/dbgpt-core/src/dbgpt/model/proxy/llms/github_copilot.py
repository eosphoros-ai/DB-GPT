import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union, cast

from dbgpt.core import ModelMetadata
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.util.i18n_utils import _

from ..base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    register_proxy_model_adapter,
)
from .chatgpt import OpenAICompatibleDeployModelParameters, OpenAILLMClient

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o"

# GitHub Copilot only accepts OAuth tokens (device flow); Personal Access
# Tokens are rejected. The GitHub token is exchanged for a short-lived
# (~30 min) Copilot API token, and chat traffic goes to the plan-specific
# endpoint exposed by ``copilot_internal/user``.
_GITHUB_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
_GITHUB_USER_ENDPOINT_URL = "https://api.github.com/copilot_internal/user"
_COPILOT_DEFAULT_BASE = "https://api.githubcopilot.com"
_COPILOT_REFRESH_MARGIN_SECS = 5 * 60

_COPILOT_HEADERS = {
    "Editor-Version": "DB-GPT/1.0",
    "Editor-Plugin-Version": "dbgpt-copilot/1.0",
    "Copilot-Integration-Id": "dbgpt-chat",
}


@auto_register_resource(
    label=_("GitHub Copilot Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("GitHub Copilot proxy LLM configuration."),
    documentation_url="https://docs.github.com/en/copilot",
    show_in_ui=False,
)
@dataclass
class GithubCopilotDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for GitHub Copilot API.

    The ``api_key`` is a GitHub OAuth token obtained via the device flow
    (Personal Access Tokens are rejected by GitHub); it is exchanged for a
    short-lived Copilot API token transparently.
    """

    provider: str = "proxy/github_copilot"

    api_base: Optional[str] = field(
        default="${env:GITHUB_COPILOT_API_BASE:-}",
        metadata={
            "help": _(
                "The base url of the GitHub Copilot API. Leave empty to use "
                "the plan-specific endpoint resolved automatically."
            ),
        },
    )

    api_key: Optional[str] = field(
        default="${env:GITHUB_COPILOT_PAT}",
        metadata={
            "help": _(
                "The GitHub OAuth token used to obtain Copilot tokens "
                "(obtained via the device-flow sign-in)."
            ),
            "tags": "privacy",
        },
    )


async def github_copilot_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: GithubCopilotLLMClient = cast(
        GithubCopilotLLMClient, model.proxy_llm_client
    )
    client.ensure_fresh_token()
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class GithubCopilotLLMClient(OpenAILLMClient):
    """GitHub Copilot LLM Client.

    The Copilot chat API is OpenAI-compatible, but GitHub only accepts OAuth
    tokens (device flow) for Copilot — Personal Access Tokens are rejected.
    The OAuth token is exchanged for a short-lived Copilot API token, and the
    chat endpoint is resolved per Copilot plan (e.g.
    ``https://api.individual.githubcopilot.com``). The exchange happens lazily
    and the underlying OpenAI client is rebuilt whenever the Copilot token is
    about to expire.

    API Reference: https://docs.github.com/en/copilot
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _DEFAULT_MODEL,
        proxies: Optional[Any] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["AsyncOpenAI"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = api_base or os.getenv("GITHUB_COPILOT_API_BASE") or None
        # The GitHub credential (OAuth token from the device flow; PATs are
        # rejected by GitHub for Copilot) is kept separate from the short-lived
        # Copilot token handed to the OpenAI client below.
        self._github_token = (
            api_key or os.getenv("GITHUB_COPILOT_PAT") or os.getenv("GITHUB_TOKEN")
        )
        model = model or _DEFAULT_MODEL
        if not self._github_token:
            raise ValueError(
                "GitHub Copilot requires GitHub sign-in (OAuth device flow), "
                "please connect the provider from the settings page or set "
                "'GITHUB_COPILOT_PAT' to a GitHub token."
            )
        self._api_base = api_base
        self._copilot_token: Optional[str] = None
        self._copilot_expires_at: float = 0.0
        # Pass a placeholder key so the parent's eager client build does not
        # fail; _apply_token below replaces the client with a real one.
        super().__init__(
            api_key="placeholder",
            api_base=api_base or _COPILOT_DEFAULT_BASE,
            api_type=api_type,
            api_version=api_version,
            model=model,
            proxies=proxies,
            timeout=timeout,
            model_alias=model_alias,
            context_length=context_length,
            openai_client=openai_client,
            openai_kwargs=openai_kwargs,
            **kwargs,
        )
        if openai_client is None:
            self._apply_token(self._exchange_token())

    def _resolve_chat_base(self) -> str:
        """Resolve the plan-specific Copilot chat endpoint.

        Newer GitHub plans route chat traffic through per-plan domains (e.g.
        ``https://api.individual.githubcopilot.com``); the endpoint is exposed
        by the ``copilot_internal/user`` endpoint.
        """
        import httpx

        try:
            resp = httpx.get(
                _GITHUB_USER_ENDPOINT_URL,
                headers={
                    "Authorization": f"Bearer {self._github_token}",
                    "Accept": "application/json",
                    **_COPILOT_HEADERS,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                api = (resp.json().get("endpoints") or {}).get("api")
                if api:
                    return api
        except Exception as e:
            logger.warning(f"resolve copilot chat endpoint failed: {e}")
        return _COPILOT_DEFAULT_BASE

    def _exchange_token(self) -> Dict[str, Any]:
        """Exchange the GitHub token for a short-lived Copilot API token."""
        import httpx

        resp = httpx.get(
            _GITHUB_TOKEN_URL,
            headers={
                "Authorization": f"Bearer {self._github_token}",
                "Accept": "application/json",
                **_COPILOT_HEADERS,
            },
            timeout=15,
        )
        if resp.status_code == 404:
            raise ValueError(
                "GitHub rejected the Copilot token exchange (HTTP 404): "
                "Personal Access Tokens are not supported for Copilot; sign "
                "in with the GitHub OAuth device flow instead."
            )
        if resp.status_code != 200:
            raise ValueError(
                f"Copilot token exchange failed with HTTP {resp.status_code}; "
                f"check that the account has an active Copilot subscription."
            )
        data = resp.json()
        if not data.get("token"):
            raise ValueError("GitHub Copilot token exchange returned no token")
        return data

    def _apply_token(self, token_data: Dict[str, Any]) -> None:
        """Rebuild the underlying OpenAI client with a fresh Copilot token."""
        import httpx
        from openai import AsyncOpenAI

        self._copilot_token = token_data["token"]
        self._copilot_expires_at = float(token_data.get("expires_at") or 0)
        self._client = AsyncOpenAI(
            api_key=self._copilot_token,
            base_url=self._api_base or self._resolve_chat_base(),
            http_client=httpx.AsyncClient(),
            default_headers=dict(_COPILOT_HEADERS),
        )

    def ensure_fresh_token(self) -> None:
        """Refresh the Copilot token if it is missing or close to expiry."""
        if (
            not self._copilot_token
            or time.time() >= self._copilot_expires_at - _COPILOT_REFRESH_MARGIN_SECS
        ):
            self._apply_token(self._exchange_token())

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[GithubCopilotDeployModelParameters]:
        """Get the deploy model parameters class."""
        return GithubCopilotDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return github_copilot_generate_stream


register_proxy_model_adapter(
    GithubCopilotLLMClient,
    supported_models=[
        ModelMetadata(
            model="gpt-4o",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4o via GitHub Copilot",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-4.1",
            context_length=128 * 1024,
            max_output_length=32 * 1024,
            description="GPT-4.1 via GitHub Copilot",
            function_calling=True,
        ),
        ModelMetadata(
            model="o3",
            context_length=200 * 1024,
            max_output_length=100 * 1024,
            description="OpenAI o3 reasoning model via GitHub Copilot",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-sonnet-4",
            context_length=200 * 1024,
            max_output_length=64 * 1024,
            description="Claude Sonnet 4 via GitHub Copilot",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-3.7-sonnet",
            context_length=200 * 1024,
            max_output_length=64 * 1024,
            description="Claude 3.7 Sonnet via GitHub Copilot",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-2.5-pro",
            context_length=1024 * 1024,
            max_output_length=64 * 1024,
            description="Gemini 2.5 Pro via GitHub Copilot",
            function_calling=True,
        ),
        # Model availability depends on the Copilot plan; see
        # https://docs.github.com/en/copilot/ai-models
    ],
)
