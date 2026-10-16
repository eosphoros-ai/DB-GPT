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


_CHEAPER_INFERENCE_DEFAULT_MODEL = "gpt-5.4"


@auto_register_resource(
    label=_("Cheaper Inference Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Cheaper Inference proxy LLM configuration."),
    documentation_url="https://cheaperinference.com/docs",
    show_in_ui=False,
)
@dataclass
class CheaperInferenceDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Cheaper Inference."""

    provider: str = "proxy/cheaperinference"

    api_base: Optional[str] = field(
        default=(
            "${env:CHEAPER_INFERENCE_API_BASE:-https://api.cheaperinference.com/v1}"
        ),
        metadata={"help": _("The base url of the Cheaper Inference API.")},
    )

    api_key: Optional[str] = field(
        default="${env:CHEAPER_INFERENCE_API_KEY}",
        metadata={
            "help": _("The API key of the Cheaper Inference API."),
            "tags": "privacy",
        },
    )


async def cheaperinference_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: CheaperInferenceLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class CheaperInferenceLLMClient(OpenAILLMClient):
    """Cheaper Inference LLM Client using OpenAI-compatible endpoints.

    Cheaper Inference is an OpenAI-compatible LLM gateway that serves models
    from OpenAI, Anthropic, Google, DeepSeek, Z.ai, Moonshot, Qwen and others
    behind one endpoint and one API key. Model ids are bare rather than
    prefixed with the upstream vendor, for example ``gpt-5.4``,
    ``claude-opus-5`` or ``deepseek-v4-pro``; the public list is at
    https://cheaperinference.com/#models.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _CHEAPER_INFERENCE_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _CHEAPER_INFERENCE_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("CHEAPER_INFERENCE_API_BASE")
            or "https://api.cheaperinference.com/v1"
        )
        api_key = api_key or os.getenv("CHEAPER_INFERENCE_API_KEY")
        model = model or _CHEAPER_INFERENCE_DEFAULT_MODEL
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "Cheaper Inference API key is required, please set "
                "'CHEAPER_INFERENCE_API_KEY' in environment or pass it as an "
                "argument."
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
            model = _CHEAPER_INFERENCE_DEFAULT_MODEL
        return model

    @classmethod
    def new_client(
        cls,
        model_params: CheaperInferenceDeployModelParameters,
        default_executor=None,
    ) -> "CheaperInferenceLLMClient":
        """Create a new client with the model parameters.

        Overridden to pass ``context_length`` through untouched, as
        ``SynthoraiLLMClient`` and ``DeepseekLLMClient`` do. The inherited
        version clamps an unset window to 8192, which would stop the
        constructor's own 128K default from applying.
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
    def param_class(cls) -> Type[CheaperInferenceDeployModelParameters]:
        return CheaperInferenceDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return cheaperinference_generate_stream


# A short list of popular chat models. The gateway serves more models; the
# full list is at https://cheaperinference.com/#models and at
# ``GET /v1/models`` (which requires an API key). Context and output limits are
# the values that endpoint reports. Cheaper Inference has no embeddings
# endpoint, so no embedding models are registered.
register_proxy_model_adapter(
    CheaperInferenceLLMClient,
    supported_models=[
        ModelMetadata(
            model=[
                "gpt-5.4",
            ],
            context_length=1000000,
            max_output_length=131072,
            description="OpenAI GPT models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-5.5",
            ],
            context_length=1000000,
            max_output_length=128000,
            description="OpenAI GPT models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-5.4-mini",
            ],
            context_length=400000,
            max_output_length=128000,
            description="OpenAI GPT models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-opus-5",
            ],
            context_length=1000000,
            max_output_length=128000,
            description="Anthropic Claude models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-sonnet-5",
            ],
            context_length=1000000,
            max_output_length=64000,
            description="Anthropic Claude models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-haiku-4.5",
            ],
            context_length=200000,
            max_output_length=64000,
            description="Anthropic Claude models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gemini-3.1-pro",
            ],
            context_length=1048576,
            max_output_length=65536,
            description="Google Gemini models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gemini-2.5-flash",
            ],
            context_length=1048576,
            max_output_length=65535,
            description="Google Gemini models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek-v4-pro",
                "deepseek-v4-flash",
            ],
            context_length=1000000,
            max_output_length=128000,
            description="DeepSeek models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "glm-5.3",
            ],
            context_length=1000000,
            max_output_length=131072,
            description="Z.ai GLM models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "kimi-k3",
            ],
            context_length=1000000,
            max_output_length=131072,
            description="Moonshot Kimi models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "grok-4.5",
            ],
            context_length=500000,
            max_output_length=128000,
            description="xAI Grok models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen-3-8-max",
            ],
            context_length=1000000,
            max_output_length=131072,
            description="Qwen models via Cheaper Inference",
            link="https://cheaperinference.com/#models",
            function_calling=True,
        ),
    ],
)
