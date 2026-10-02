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

_DEFAULT_MODEL = "mistral-large-latest"


@auto_register_resource(
    label=_("Mistral Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Mistral AI proxy LLM configuration."),
    documentation_url="https://docs.mistral.ai",
    show_in_ui=False,
)
@dataclass
class MistralDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Mistral AI API."""

    provider: str = "proxy/mistral"

    api_base: Optional[str] = field(
        default="${env:MISTRAL_API_BASE:-https://api.mistral.ai/v1}",
        metadata={
            "help": _("The base url of the Mistral AI API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:MISTRAL_API_KEY}",
        metadata={
            "help": _("The API key of the Mistral AI API."),
            "tags": "privacy",
        },
    )


async def mistral_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: MistralLLMClient = cast(MistralLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class MistralLLMClient(OpenAILLMClient):
    """Mistral AI LLM Client.

    Mistral AI API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.

    API Reference: https://docs.mistral.ai
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
            api_base or os.getenv("MISTRAL_API_BASE") or "https://api.mistral.ai/v1"
        )
        api_key = api_key or os.getenv("MISTRAL_API_KEY")
        model = model or _DEFAULT_MODEL

        if not api_key:
            raise ValueError(
                "Mistral AI API key is required, please set 'MISTRAL_API_KEY' in "
                "environment variable or pass it to the client."
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
    def param_class(cls) -> Type[MistralDeployModelParameters]:
        """Get the deploy model parameters class."""
        return MistralDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return mistral_generate_stream


register_proxy_model_adapter(
    MistralLLMClient,
    supported_models=[
        ModelMetadata(
            model="mistral-large-latest",
            context_length=128 * 1024,
            max_output_length=32 * 1024,
            description="Mistral Large by Mistral AI",
            link="https://docs.mistral.ai/getting-started/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="mistral-medium-latest",
            context_length=128 * 1024,
            max_output_length=32 * 1024,
            description="Mistral Medium by Mistral AI",
            link="https://docs.mistral.ai/getting-started/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="mistral-small-latest",
            context_length=128 * 1024,
            max_output_length=32 * 1024,
            description="Mistral Small by Mistral AI",
            link="https://docs.mistral.ai/getting-started/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="codestral-latest",
            context_length=256 * 1024,
            max_output_length=32 * 1024,
            description="Codestral by Mistral AI",
            link="https://docs.mistral.ai/getting-started/models",
            function_calling=True,
        ),
        # More models at: https://docs.mistral.ai/getting-started/models
    ],
)
