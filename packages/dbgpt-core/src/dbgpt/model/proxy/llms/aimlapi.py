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

AIMLAPI_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_AIMLAPI_DEFAULT_MODEL = "gpt-4o"


@auto_register_resource(
    label=_("AI/ML API Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("AI/ML API proxy LLM configuration."),
    documentation_url="https://api.aimlapi.com/v1/",
    show_in_ui=False,
)
@dataclass
class AimlapiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for AI/ML API."""

    provider: str = "proxy/aimlapi"

    api_base: Optional[str] = field(
        default="${env:AIMLAPI_API_BASE:-https://api.aimlapi.com/v1}",
        metadata={"help": _("The base url of the AI/ML API.")},
    )

    api_key: Optional[str] = field(
        default="${env:AIMLAPI_API_KEY}",
        metadata={"help": _("The API key of the AI/ML API."), "tags": "privacy"},
    )


async def aimlapi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: AimlapiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class AimlapiLLMClient(OpenAILLMClient):
    """AI/ML API LLM Client using OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _AIMLAPI_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _AIMLAPI_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("AIMLAPI_API_BASE") or "https://api.aimlapi.com/v1"
        )
        api_key = api_key or os.getenv("AIMLAPI_API_KEY")
        model = model or _AIMLAPI_DEFAULT_MODEL
        if not context_length:
            if "200k" in model:
                context_length = 200 * 1024
            else:
                context_length = 4096

        if not api_key:
            raise ValueError(
                "AI/ML API key is required, please set 'AIMLAPI_API_KEY' "
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
            self.client.default_headers.update(AIMLAPI_HEADERS)
        except Exception:
            pass

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _AIMLAPI_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[AimlapiDeployModelParameters]:
        return AimlapiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return aimlapi_generate_stream


register_proxy_model_adapter(
    AimlapiLLMClient,
    supported_models=[
        ModelMetadata(
            model=["openai/gpt-4"],
            context_length=8_000,
            max_output_length=4_096,
            description="OpenAI GPT‑4: state‑of‑the‑art language model",
            link="https://aimlapi.com/models/chat-gpt-4",
            function_calling=True,
        ),
        ModelMetadata(
            model=["openai/gpt-4o", "gpt-4o-mini", "openai/gpt-4-turbo"],
            context_length=128_000,
            max_output_length=16_384,
            description="GPT‑4 family (4o, 4o‑mini, 4 Turbo) via AI/ML API",
            link="https://aimlapi.com/models#openai-gpt-4o",
            function_calling=True,
        ),
        ModelMetadata(
            model=["gpt-3.5-turbo"],
            context_length=16_000,
            max_output_length=4_096,
            description="GPT‑3.5 Turbo: fast, high‑quality text generation",
            link="https://aimlapi.com/models/chat-gpt-3-5-turbo",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "mistralai/Mistral-7B-Instruct-v0.3",
                "meta-llama/Llama-3.1-405B",
                "Qwen/Qwen2-235B",
            ],
            context_length=32_000,
            max_output_length=8_192,
            description="Instruction‑tuned LLMs with 32k token context window",
            link="https://aimlapi.com/models",
            function_calling=False,
        ),
        ModelMetadata(
            model=[
                "google/gemini-2-27b-it",
                "x-ai/grok-2-beta",
                "bytedance/seedream-3.0",
            ],
            context_length=8_000,
            max_output_length=4_096,
            description="Models with 8k token context window, no function_calling",
            link="https://aimlapi.com/models",
            function_calling=False,
        ),
        ModelMetadata(
            model=["claude-3-5-sonnet-20240620"],
            context_length=8_192,
            max_output_length=2_048,
            description="Claude 3.5 Sonnet: advanced multimodal model from Anthropic",
            link="https://aimlapi.com/models/claude-3-5-sonnet",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek-chat"],
            context_length=128_000,
            max_output_length=16_000,
            description="DeepSeek V3: efficient high‑performance LLM",
            link="https://aimlapi.com/models/deepseek-v3",
            function_calling=False,
        ),
        ModelMetadata(
            model=["mistralai/Mixtral-8x7B-Instruct-v0.1"],
            context_length=64_000,
            max_output_length=8_000,
            description="Mixtral‑8x7B: sparse mixture‑of‑experts instruction model",
            link="https://aimlapi.com/models/mixtral-8x7b-instruct-v01",
            function_calling=False,
        ),
        ModelMetadata(
            model=["meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo"],
            context_length=131_000,
            max_output_length=16_000,
            description="Llama 3.2‑90B: advanced vision‑instruct turbo model",
            link="https://aimlapi.com/models/llama-3-2-90b-vision-instruct-turbo-api",
            function_calling=False,
        ),
        ModelMetadata(
            model=["google/gemini-2-0-flash"],
            context_length=1_000_000,
            max_output_length=32_768,
            description="Gemini 2.0 Flash: ultra‑low latency multimodal model",
            link="https://aimlapi.com/models/gemini-2-0-flash-api",
            function_calling=True,
        ),
        ModelMetadata(
            model=["meta-llama/Meta-Llama-3-8B-Instruct-Lite"],
            context_length=9_000,
            max_output_length=1_024,
            description="Llama 3 8B Instruct Lite: compact dialogue model",
            link="https://aimlapi.com/models/llama-3-8b-instruct-lite-api",
            function_calling=False,
        ),
        ModelMetadata(
            model=["cohere/command-r-plus"],
            context_length=128_000,
            max_output_length=16_000,
            description="Cohere Command R+: enterprise‑grade chat model",
            link="https://aimlapi.com/models/command-r-api",
            function_calling=False,
        ),
        ModelMetadata(
            model=["mistralai/codestral-2501"],
            context_length=256_000,
            max_output_length=32_000,
            description="Codestral‑2501: advanced code generation model",
            link="https://aimlapi.com/models/mistral-codestral-2501-api",
            function_calling=False,
        ),
    ],
)
