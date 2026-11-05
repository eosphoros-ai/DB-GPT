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


_OPPER_DEFAULT_MODEL = "claude-sonnet-4-6"


@auto_register_resource(
    label=_("Opper Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Opper proxy LLM configuration."),
    documentation_url="https://docs.opper.ai",
    show_in_ui=False,
)
@dataclass
class OpperDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Opper."""

    provider: str = "proxy/opper"

    api_base: Optional[str] = field(
        default="${env:OPPER_API_BASE:-https://api.opper.ai/v3/compat}",
        metadata={"help": _("The base url of the Opper API.")},
    )

    api_key: Optional[str] = field(
        default="${env:OPPER_API_KEY}",
        metadata={"help": _("The API key of the Opper API."), "tags": "privacy"},
    )


async def opper_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: OpperLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class OpperLLMClient(OpenAILLMClient):
    """Opper LLM Client using OpenAI-compatible endpoints.

    Opper is an EU-hosted AI gateway with 700+ models from 50+ providers behind
    one OpenAI-compatible API and one key. Model ids are bare pool names, for
    example ``claude-sonnet-4-6``, ``gpt-5.5`` or ``deepseek-v4-pro``, and Opper
    picks the route for each request. A ``provider/model`` id such as
    ``anthropic/claude-sonnet-4-6`` pins a single route.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _OPPER_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = None,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("OPPER_API_BASE") or "https://api.opper.ai/v3/compat"
        )
        api_key = api_key or os.getenv("OPPER_API_KEY")
        model = model or _OPPER_DEFAULT_MODEL
        model_alias = model_alias or model
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "Opper API key is required, please set 'OPPER_API_KEY' "
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
            model = _OPPER_DEFAULT_MODEL
        return model

    @classmethod
    def new_client(
        cls,
        model_params: OpperDeployModelParameters,
        default_executor=None,
    ) -> "OpperLLMClient":
        """Create a new client with the model parameters.

        Overridden to pass ``context_length`` through untouched, as
        ``DeepseekLLMClient.new_client`` does. The inherited version turns an
        unset value into 8192, so the 128K default above would never apply.
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
    def param_class(cls) -> Type[OpperDeployModelParameters]:
        return OpperDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return opper_generate_stream


# Context and output limits match Opper's models.dev entry and the public
# catalogue at https://api.opper.ai/v3/models. The first five models are the
# ones the Model Providers page enables by default when Opper is connected.
register_proxy_model_adapter(
    OpperLLMClient,
    supported_models=[
        ModelMetadata(
            model="claude-sonnet-4-6",
            context_length=1_000_000,
            max_output_length=64_000,
            description="Anthropic Claude Sonnet 4.6 via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-opus-5",
            context_length=1_000_000,
            max_output_length=128_000,
            description="Anthropic Claude Opus 5 via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-5.5",
            context_length=1_050_000,
            max_output_length=128_000,
            description="OpenAI GPT-5.5 via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-5.4-mini",
            context_length=400_000,
            max_output_length=128_000,
            description="OpenAI GPT-5.4 mini via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-3.8-flash",
            context_length=1_048_576,
            max_output_length=65_536,
            description="Google Gemini 3.8 Flash via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-v4-pro",
            context_length=1_000_000,
            max_output_length=65_536,
            description="DeepSeek V4 Pro via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="kimi-k3",
            context_length=1_048_576,
            max_output_length=131_072,
            description="Moonshot Kimi K3 via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="glm-5.3",
            context_length=1_000_000,
            max_output_length=131_072,
            description="Z.ai GLM-5.3 via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="qwen3.8-max",
            context_length=983_616,
            max_output_length=131_072,
            description="Qwen3.8 Max via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="mistral-large-2512",
            context_length=256_000,
            max_output_length=8_192,
            description="Mistral Large via Opper",
            link="https://opper.ai/models",
            function_calling=True,
        ),
    ],
)
