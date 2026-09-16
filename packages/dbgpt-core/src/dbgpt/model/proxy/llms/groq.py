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

_DEFAULT_MODEL = "llama-3.3-70b-versatile"


@auto_register_resource(
    label=_("Groq Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Groq proxy LLM configuration."),
    documentation_url="https://console.groq.com/docs/api-reference",
    show_in_ui=False,
)
@dataclass
class GroqDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Groq API."""

    provider: str = "proxy/groq"

    api_base: Optional[str] = field(
        default="${env:GROQ_API_BASE:-https://api.groq.com/openai/v1}",
        metadata={
            "help": _("The base url of the Groq API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:GROQ_API_KEY}",
        metadata={
            "help": _("The API key of the Groq API."),
            "tags": "privacy",
        },
    )


async def groq_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: GroqLLMClient = cast(GroqLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class GroqLLMClient(OpenAILLMClient):
    """Groq LLM Client.

    Groq API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.

    API Reference: https://console.groq.com/docs/api-reference
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
            api_base or os.getenv("GROQ_API_BASE") or "https://api.groq.com/openai/v1"
        )
        api_key = api_key or os.getenv("GROQ_API_KEY")
        model = model or _DEFAULT_MODEL

        if not api_key:
            raise ValueError(
                "Groq API key is required, please set 'GROQ_API_KEY' in "
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
    def param_class(cls) -> Type[GroqDeployModelParameters]:
        """Get the deploy model parameters class."""
        return GroqDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return groq_generate_stream


register_proxy_model_adapter(
    GroqLLMClient,
    supported_models=[
        ModelMetadata(
            model="llama-3.3-70b-versatile",
            context_length=128 * 1024,
            max_output_length=32 * 1024,
            description="Llama 3.3 70B Versatile on Groq",
            link="https://console.groq.com/docs/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="llama-3.1-8b-instant",
            context_length=128 * 1024,
            max_output_length=32 * 1024,
            description="Llama 3.1 8B Instant on Groq",
            link="https://console.groq.com/docs/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="openai/gpt-oss-120b",
            context_length=131 * 1024,
            max_output_length=32 * 1024,
            description="GPT-OSS 120B on Groq",
            link="https://console.groq.com/docs/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="qwen/qwen3-32b",
            context_length=131 * 1024,
            max_output_length=40 * 1024,
            description="Qwen3 32B on Groq",
            link="https://console.groq.com/docs/models",
            function_calling=True,
        ),
        # More models at: https://console.groq.com/docs/models
    ],
)
