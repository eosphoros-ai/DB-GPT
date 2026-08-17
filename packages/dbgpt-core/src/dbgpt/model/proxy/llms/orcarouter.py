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

ORCAROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_ORCAROUTER_DEFAULT_MODEL = "openai/gpt-4o"


@auto_register_resource(
    label=_("OrcaRouter Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("OrcaRouter proxy LLM configuration."),
    documentation_url="https://docs.orcarouter.ai",
    show_in_ui=False,
)
@dataclass
class OrcaRouterDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for OrcaRouter."""

    provider: str = "proxy/orcarouter"

    api_base: Optional[str] = field(
        default="${env:ORCAROUTER_API_BASE:-https://api.orcarouter.ai/v1}",
        metadata={"help": _("The base url of the OrcaRouter API.")},
    )

    api_key: Optional[str] = field(
        default="${env:ORCAROUTER_API_KEY}",
        metadata={"help": _("The API key of the OrcaRouter API."), "tags": "privacy"},
    )


async def orcarouter_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: OrcaRouterLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class OrcaRouterLLMClient(OpenAILLMClient):
    """OrcaRouter LLM Client using OpenAI-compatible endpoints.

    OrcaRouter is a model routing gateway that exposes 150+ models from OpenAI,
    Anthropic, Google, DeepSeek, Qwen, GLM and others behind a single OpenAI
    compatible endpoint and API key. Model ids keep their provider prefix, for
    example ``openai/gpt-4o``, ``anthropic/claude-opus-4.8`` or
    ``deepseek/deepseek-chat``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _ORCAROUTER_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _ORCAROUTER_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("ORCAROUTER_API_BASE")
            or "https://api.orcarouter.ai/v1"
        )
        api_key = api_key or os.getenv("ORCAROUTER_API_KEY")
        model = model or _ORCAROUTER_DEFAULT_MODEL
        if not context_length:
            if "gpt-3.5" in model:
                context_length = 16 * 1024
            else:
                context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "OrcaRouter API key is required, please set 'ORCAROUTER_API_KEY' "
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
            self.client.default_headers.update(ORCAROUTER_HEADERS)
        except Exception:
            pass

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _ORCAROUTER_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[OrcaRouterDeployModelParameters]:
        return OrcaRouterDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return orcarouter_generate_stream


register_proxy_model_adapter(
    OrcaRouterLLMClient,
    supported_models=[
        ModelMetadata(
            model=[
                "orcarouter/fusion",
                "orcarouter/fusion-mini",
                "orcarouter/fusion-flash",
            ],
            context_length=1_000_000,
            max_output_length=32_768,
            description=(
                "OrcaRouter routing models that pick the best upstream model "
                "for each request"
            ),
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["openai/gpt-4o", "openai/gpt-4o-mini"],
            context_length=128_000,
            max_output_length=16_384,
            description="OpenAI GPT-4 family models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["openai/gpt-5.2", "openai/gpt-5.2-pro", "openai/gpt-5.4-mini"],
            context_length=400_000,
            max_output_length=32_768,
            description="OpenAI GPT-5 family models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "anthropic/claude-opus-4.8",
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-haiku-4.5",
            ],
            context_length=1_000_000,
            max_output_length=32_768,
            description="Anthropic Claude family models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek/deepseek-chat",
                "deepseek/deepseek-reasoner",
                "deepseek/deepseek-v4-pro",
            ],
            context_length=1_048_576,
            max_output_length=16_384,
            description="DeepSeek models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "google/gemini-2.5-flash",
                "google/gemini-2.5-pro",
                "google/gemini-3.5-flash",
            ],
            context_length=1_048_576,
            max_output_length=32_768,
            description="Google Gemini family models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["qwen/qwen3.8-max", "qwen/qwen3.6-flash"],
            context_length=1_000_000,
            max_output_length=16_384,
            description="Qwen models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["z-ai/glm-5.2", "z-ai/glm-4.7"],
            context_length=1_000_000,
            max_output_length=16_384,
            description="GLM models via OrcaRouter",
            link="https://www.orcarouter.ai/models",
            function_calling=True,
        ),
    ],
)
