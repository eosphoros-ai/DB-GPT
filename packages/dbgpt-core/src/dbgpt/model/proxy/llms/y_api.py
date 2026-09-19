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

YAPI_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_YAPI_DEFAULT_MODEL = "deepseek/deepseek-v4-flash"


@auto_register_resource(
    label=_("Y-API Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Y-API proxy LLM configuration."),
    documentation_url="https://y-api.bestvirtualgoods.com/models",
    show_in_ui=False,
)
@dataclass
class YApiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Y-API."""

    provider: str = "proxy/y-api"

    api_base: Optional[str] = field(
        default="${env:YAPI_API_BASE:-https://api.y-api.bestvirtualgoods.com/v1}",
        metadata={"help": _("The base url of the Y-API.")},
    )

    api_key: Optional[str] = field(
        default="${env:YAPI_API_KEY}",
        metadata={"help": _("The API key of the Y-API."), "tags": "privacy"},
    )


async def yapi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: YApiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class YApiLLMClient(OpenAILLMClient):
    """Y-API LLM Client using OpenAI-compatible endpoints.

    Y-API is a gateway that fronts several vendors behind a single
    OpenAI-compatible endpoint and API key, so model ids keep their vendor
    prefix: ``deepseek/deepseek-v4-flash``, ``z-ai/glm-5.3`` or
    ``openai/gpt-5.6-sol``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _YAPI_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _YAPI_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("YAPI_API_BASE")
            or "https://api.y-api.bestvirtualgoods.com/v1"
        )
        api_key = api_key or os.getenv("YAPI_API_KEY")
        model = model or _YAPI_DEFAULT_MODEL
        # The smallest window any catalog model advertises is 256K, so 128K is a
        # conservative fallback for a model this client has no metadata for.
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "Y-API key is required, please set 'YAPI_API_KEY' "
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
            self.client.default_headers.update(YAPI_HEADERS)
        except Exception:
            pass

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _YAPI_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[YApiDeployModelParameters]:
        return YApiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return yapi_generate_stream


register_proxy_model_adapter(
    YApiLLMClient,
    supported_models=[
        # Context windows are measured against the live gateway by overflowing the
        # window, except for the four models noted as OpenRouter-derived below.
        # max_output_length is OpenRouter's default_max_tokens throughout - the
        # gateway does not publish an output cap.
        #
        # qwen/qwen3.8-flash is deliberately absent: GET /v1/models lists it, but
        # POST /v1/chat/completions answers 400 "Requested model
        # Qwen3.8-Flash-Next not supported", so offering it here would only give
        # users a model that cannot answer.
        ModelMetadata(
            model=[
                "deepseek/deepseek-v4-flash",
                "deepseek/deepseek-v4-pro",
            ],
            context_length=1_048_576,
            max_output_length=196_608,
            description=(
                "DeepSeek V4 models via Y-API (context length OpenRouter-derived)"
            ),
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek/deepseek-v4.1-flash"],
            context_length=1_048_544,
            max_output_length=192_000,
            description="DeepSeek V4.1 Flash via Y-API",
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek/deepseek-v4-flash-0731"],
            context_length=1_048_544,
            max_output_length=589_824,
            description="DeepSeek V4 Flash (0731) via Y-API",
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "z-ai/glm-5.2",
                "z-ai/glm-5.3",
                "z-ai/glm-5.3-flash",
            ],
            context_length=1_048_544,
            max_output_length=589_824,
            description="GLM models via Y-API",
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["moonshotai/kimi-k3"],
            context_length=1_048_544,
            max_output_length=471_859,
            description="Kimi K3 via Y-API",
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["tencent/hy3"],
            context_length=262_144,
            max_output_length=65_536,
            description=(
                "Tencent Hunyuan 3 via Y-API (context length OpenRouter-derived)"
            ),
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["xiaomi/mimo-v2.5"],
            context_length=1_048_576,
            max_output_length=65_536,
            description=(
                "Xiaomi MiMo v2.5 via Y-API (context length OpenRouter-derived)"
            ),
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "openai/gpt-6-astra",
                "openai/gpt-5.6-sol",
                "openai/gpt-5.6-terra",
                "openai/gpt-5.6-luna",
            ],
            context_length=922_000,
            max_output_length=64_000,
            description="OpenAI GPT models via Y-API",
            link="https://y-api.bestvirtualgoods.com/models",
            function_calling=True,
        ),
    ],
)
