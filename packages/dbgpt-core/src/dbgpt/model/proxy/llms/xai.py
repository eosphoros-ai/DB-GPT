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

_DEFAULT_MODEL = "grok-4"


@auto_register_resource(
    label=_("xAI Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("xAI Grok proxy LLM configuration."),
    documentation_url="https://docs.x.ai",
    show_in_ui=False,
)
@dataclass
class XaiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for xAI Grok API."""

    provider: str = "proxy/xai"

    api_base: Optional[str] = field(
        default="${env:XAI_API_BASE:-https://api.x.ai/v1}",
        metadata={
            "help": _("The base url of the xAI API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:XAI_API_KEY}",
        metadata={
            "help": _("The API key of the xAI API."),
            "tags": "privacy",
        },
    )


async def xai_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: XaiLLMClient = cast(XaiLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class XaiLLMClient(OpenAILLMClient):
    """xAI Grok LLM Client.

    xAI API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.

    API Reference: https://docs.x.ai
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
        api_base = api_base or os.getenv("XAI_API_BASE") or "https://api.x.ai/v1"
        api_key = api_key or os.getenv("XAI_API_KEY")
        model = model or _DEFAULT_MODEL

        if not api_key:
            raise ValueError(
                "xAI API key is required, please set 'XAI_API_KEY' in "
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
    def param_class(cls) -> Type[XaiDeployModelParameters]:
        """Get the deploy model parameters class."""
        return XaiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return xai_generate_stream


register_proxy_model_adapter(
    XaiLLMClient,
    supported_models=[
        ModelMetadata(
            model="grok-4",
            context_length=256 * 1024,
            max_output_length=32 * 1024,
            description="Grok 4 by xAI",
            link="https://docs.x.ai/docs/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="grok-4-fast",
            context_length=256 * 1024,
            max_output_length=32 * 1024,
            description="Grok 4 Fast by xAI",
            link="https://docs.x.ai/docs/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="grok-3",
            context_length=131 * 1024,
            max_output_length=32 * 1024,
            description="Grok 3 by xAI",
            link="https://docs.x.ai/docs/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="grok-3-mini",
            context_length=131 * 1024,
            max_output_length=32 * 1024,
            description="Grok 3 Mini by xAI",
            link="https://docs.x.ai/docs/models",
            function_calling=True,
        ),
        # More models at: https://docs.x.ai/docs/models
    ],
)
