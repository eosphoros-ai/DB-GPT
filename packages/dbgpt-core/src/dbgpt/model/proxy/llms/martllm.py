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

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_MARTLLM_DEFAULT_MODEL = "openai/gpt-4o"


@auto_register_resource(
    label=_("MartLLM Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("MartLLM proxy LLM configuration."),
    documentation_url="https://martllm.com/docs/quickstart",
    show_in_ui=False,
)
@dataclass
class MartLLMDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for MartLLM."""

    provider: str = "proxy/martllm"

    api_base: Optional[str] = field(
        default="${env:MARTLLM_API_BASE:-https://api.martllm.com/v1}",
        metadata={"help": _("The base url of the MartLLM API.")},
    )

    api_key: Optional[str] = field(
        default="${env:MARTLLM_API_KEY}",
        metadata={"help": _("The API key of the MartLLM API."), "tags": "privacy"},
    )


async def martllm_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: MartLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class MartLLMClient(OpenAILLMClient):
    """MartLLM LLM Client using OpenAI-compatible endpoints.

    MartLLM serves chat models from OpenAI, Anthropic, Google, DeepSeek, Qwen,
    Z.ai and others behind one OpenAI compatible endpoint and one prepaid API
    key. Model ids keep their vendor prefix, for example ``openai/gpt-4o``,
    ``anthropic/claude-sonnet-4.6`` or ``deepseek/deepseek-v4-flash``; the live
    list is at https://api.martllm.com/v1/models.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _MARTLLM_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _MARTLLM_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("MARTLLM_API_BASE") or "https://api.martllm.com/v1"
        )
        api_key = api_key or os.getenv("MARTLLM_API_KEY")
        model = model or _MARTLLM_DEFAULT_MODEL
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "MartLLM API key is required, please set 'MARTLLM_API_KEY' "
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

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _MARTLLM_DEFAULT_MODEL
        return model

    @classmethod
    def new_client(
        cls,
        model_params: MartLLMDeployModelParameters,
        default_executor=None,
    ) -> "MartLLMClient":
        """Create a new client with the model parameters.

        Overridden to pass ``context_length`` through untouched. The inherited
        version clamps it with ``max(model_params.context_length or 8192, 8192)``,
        so an unset window arrives as 8192 and the constructor's own 128K
        default stops applying. ``SynthoraiLLMClient`` and ``DeepseekLLMClient``
        override it for the same reason.
        """
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            api_type=model_params.api_type,
            api_version=model_params.api_version,
            model=model_params.real_provider_model_name,
            proxy=model_params.http_proxy,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
        )

    @classmethod
    def param_class(cls) -> Type[MartLLMDeployModelParameters]:
        return MartLLMDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return martllm_generate_stream


register_proxy_model_adapter(
    MartLLMClient,
    supported_models=[
        ModelMetadata(
            model=["openai/gpt-4o", "openai/gpt-4o-mini"],
            context_length=128_000,
            max_output_length=16_384,
            description="OpenAI GPT-4o family models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["openai/gpt-5.5", "openai/gpt-5.4", "openai/gpt-5.4-mini"],
            context_length=400_000,
            max_output_length=128_000,
            description="OpenAI GPT-5 family models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "anthropic/claude-opus-4.8",
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-haiku-4.5",
            ],
            context_length=200_000,
            max_output_length=64_000,
            description="Anthropic Claude family models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek/deepseek-v4-flash",
                "deepseek/deepseek-v4.1-flash",
                "deepseek/deepseek-v4-pro",
            ],
            context_length=1_000_000,
            max_output_length=128_000,
            description="DeepSeek models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "google/gemini-2.5-flash",
                "google/gemini-2.5-pro",
                "google/gemini-3.5-flash",
            ],
            context_length=1_000_000,
            max_output_length=65_535,
            description="Google Gemini family models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["qwen/qwen3.7-max", "qwen/qwen3.7-flash"],
            context_length=256_000,
            max_output_length=32_768,
            description="Qwen models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["z-ai/glm-5.2", "z-ai/glm-4.7"],
            context_length=128_000,
            max_output_length=32_768,
            description="GLM models via MartLLM",
            link="https://martllm.com/models",
            function_calling=True,
        ),
    ],
)
