import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

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

API_ROUTE_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_API_ROUTE_DEFAULT_MODEL = "deepseek/deepseek-chat"


@auto_register_resource(
    label=_("API Route Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("API Route proxy LLM configuration."),
    documentation_url="https://www.api-route.com",
    show_in_ui=False,
)
@dataclass
class ApiRouteDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for API Route."""

    provider: str = "proxy/api_route"

    api_base: Optional[str] = field(
        default="${env:API_ROUTE_API_BASE:-https://global.api-route.com/v1}",
        metadata={"help": _("The base url of the API Route API.")},
    )

    api_key: Optional[str] = field(
        default="${env:API_ROUTE_API_KEY}",
        metadata={"help": _("The API key of the API Route API."), "tags": "privacy"},
    )


async def api_route_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: ApiRouteLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class ApiRouteLLMClient(OpenAILLMClient):
    """API Route LLM Client using OpenAI-compatible endpoints.

    API Route is an AI model routing gateway that exposes 100+ models from OpenAI,
    Anthropic, Google, DeepSeek, Qwen and others behind a single OpenAI
    compatible endpoint and API key. Model ids keep their provider prefix, for
    example ``deepseek/deepseek-chat``, ``anthropic/claude-3-7-sonnet`` or
    ``openai/gpt-5``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _API_ROUTE_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _API_ROUTE_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("API_ROUTE_API_BASE")
            or "https://global.api-route.com/v1"
        )
        api_key = api_key or os.getenv("API_ROUTE_API_KEY")
        model = model or _API_ROUTE_DEFAULT_MODEL
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "API Route API key is required, please set 'API_ROUTE_API_KEY' "
                "in environment or pass it as an argument."
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
        try:
            self.client.default_headers.update(API_ROUTE_HEADERS)
        except Exception:
            pass

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _API_ROUTE_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[ApiRouteDeployModelParameters]:
        return ApiRouteDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return api_route_generate_stream


register_proxy_model_adapter(
    ApiRouteLLMClient,
    supported_models=[
        ModelMetadata(
            model=["openai/gpt-5", "openai/gpt-4.5", "openai/o3", "openai/o1"],
            context_length=128_000,
            max_output_length=16_384,
            description="OpenAI 2025/2026 flagship and reasoning models via API Route",
            link="https://www.api-route.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "anthropic/claude-3-7-sonnet",
                "anthropic/claude-3-7-sonnet:thinking",
            ],
            context_length=200_000,
            max_output_length=64_000,
            description="Anthropic Claude 3.7 family models via API Route",
            link="https://www.api-route.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek/deepseek-chat",
                "deepseek/deepseek-reasoner",
            ],
            context_length=64_000,
            max_output_length=8_192,
            description="DeepSeek V3/R1 models via API Route",
            link="https://www.api-route.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "google/gemini-2.5-flash",
                "google/gemini-2.5-pro",
            ],
            context_length=1_000_000,
            max_output_length=8_192,
            description="Google Gemini 2.5 family models via API Route",
            link="https://www.api-route.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["qwen/qwen-2.5-72b-instruct", "qwen/qwen-2.5-coder-32b-instruct"],
            context_length=128_000,
            max_output_length=8_192,
            description="Qwen 2.5 models via API Route",
            link="https://www.api-route.com/models",
            function_calling=True,
        ),
    ],
)
