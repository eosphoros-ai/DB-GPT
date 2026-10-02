import os
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
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

_DEFAULT_MODEL = "openai/gpt-4o-mini"


@auto_register_resource(
    label=_("Vercel AI Gateway Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Vercel AI Gateway proxy LLM configuration."),
    documentation_url="https://vercel.com/docs/ai-gateway",
    show_in_ui=False,
)
@dataclass
class VercelAIGatewayDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Vercel AI Gateway API."""

    provider: str = "proxy/vercel"

    api_base: Optional[str] = field(
        default="${env:VERCEL_AI_GATEWAY_API_BASE:-https://ai-gateway.vercel.sh/v1}",
        metadata={
            "help": _("The base url of the Vercel AI Gateway API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:VERCEL_AI_GATEWAY_API_KEY}",
        metadata={
            "help": _("The API key of the Vercel AI Gateway API."),
            "tags": "privacy",
        },
    )


async def vercel_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: VercelAIGatewayLLMClient = cast(
        VercelAIGatewayLLMClient, model.proxy_llm_client
    )
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class VercelAIGatewayLLMClient(OpenAILLMClient):
    """Vercel AI Gateway LLM Client.

    Vercel AI Gateway API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.

    API Reference: https://vercel.com/docs/ai-gateway
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("VERCEL_AI_GATEWAY_API_BASE")
            or "https://ai-gateway.vercel.sh/v1"
        )
        api_key = (
            api_key
            or os.getenv("VERCEL_AI_GATEWAY_API_KEY")
            or os.getenv("VERCEL_OIDC_TOKEN")
        )
        model = model or _DEFAULT_MODEL

        if not api_key:
            raise ValueError(
                "Vercel AI Gateway API key is required, please set "
                "'VERCEL_AI_GATEWAY_API_KEY' in environment variable or pass it "
                "to the client."
            )
        super().__init__(
            api_key=api_key,
            api_base=api_base,
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

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[VercelAIGatewayDeployModelParameters]:
        """Get the deploy model parameters class."""
        return VercelAIGatewayDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return vercel_generate_stream


register_proxy_model_adapter(
    VercelAIGatewayLLMClient,
    supported_models=[
        ModelMetadata(
            model="openai/gpt-5.2",
            context_length=400 * 1024,
            max_output_length=128 * 1024,
            description="GPT-5.2 via Vercel AI Gateway",
            link="https://vercel.com/ai-gateway/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="openai/gpt-4o-mini",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4o Mini via Vercel AI Gateway",
            link="https://vercel.com/ai-gateway/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="anthropic/claude-sonnet-4.5",
            context_length=200 * 1024,
            max_output_length=64 * 1024,
            description="Claude Sonnet 4.5 via Vercel AI Gateway",
            link="https://vercel.com/ai-gateway/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="google/gemini-2.5-pro",
            context_length=1024 * 1024,
            max_output_length=64 * 1024,
            description="Gemini 2.5 Pro via Vercel AI Gateway",
            link="https://vercel.com/ai-gateway/models",
            function_calling=True,
        ),
        # More models at: https://vercel.com/ai-gateway/models
    ],
)
