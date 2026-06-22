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


_ATLASCLOUD_DEFAULT_MODEL = "deepseek-ai/deepseek-v4-pro"


@auto_register_resource(
    label=_("Atlas Cloud Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Atlas Cloud proxy LLM configuration."),
    documentation_url="https://docs.atlascloud.ai/",
    show_in_ui=False,
)
@dataclass
class AtlasCloudDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Atlas Cloud."""

    provider: str = "proxy/atlascloud"

    api_base: Optional[str] = field(
        default="${env:ATLASCLOUD_API_BASE:-https://api.atlascloud.ai/v1}",
        metadata={
            "help": _("The base url of the Atlas Cloud API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:ATLASCLOUD_API_KEY}",
        metadata={
            "help": _("The API key of the Atlas Cloud API."),
            "tags": "privacy",
        },
    )


async def atlascloud_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: AtlasCloudLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class AtlasCloudLLMClient(OpenAILLMClient):
    """Atlas Cloud LLM Client.

    Atlas Cloud's API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.

    API Reference: https://docs.atlascloud.ai/
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _ATLASCLOUD_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _ATLASCLOUD_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("ATLASCLOUD_API_BASE")
            or "https://api.atlascloud.ai/v1"
        )
        api_key = api_key or os.getenv("ATLASCLOUD_API_KEY")
        model = model or _ATLASCLOUD_DEFAULT_MODEL
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "Atlas Cloud API key is required, please set 'ATLASCLOUD_API_KEY' in "
                "environment or pass it as an argument."
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
            model = _ATLASCLOUD_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[AtlasCloudDeployModelParameters]:
        return AtlasCloudDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return atlascloud_generate_stream


register_proxy_model_adapter(
    AtlasCloudLLMClient,
    supported_models=[
        ModelMetadata(
            model="deepseek-ai/deepseek-v4-pro",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V4-Pro served by Atlas Cloud",
            link="https://www.atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-ai/DeepSeek-V3",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V3 served by Atlas Cloud",
            link="https://www.atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model="Qwen/Qwen2.5-72B-Instruct",
            context_length=32 * 1024,
            max_output_length=8 * 1024,
            description="Qwen2.5-72B-Instruct served by Atlas Cloud",
            link="https://www.atlascloud.ai/models",
            function_calling=True,
        ),
        # More models see: https://www.atlascloud.ai/models
    ],
)
