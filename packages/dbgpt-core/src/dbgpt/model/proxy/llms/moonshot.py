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

_MOONSHOT_DEFAULT_MODEL = "moonshot-v1-8k"


@auto_register_resource(
    label=_("Moonshot Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Moonshot proxy LLM configuration."),
    documentation_url="https://platform.moonshot.cn/docs/api/chat#%E5%85%AC%E5%BC%80%E7%9A%84%E6%9C%8D%E5%8A%A1%E5%9C%B0%E5%9D%80",  # noqa
    show_in_ui=False,
)
@dataclass
class MoonshotDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Moonshot."""

    provider: str = "proxy/moonshot"

    api_base: Optional[str] = field(
        default="${env:MOONSHOT_API_BASE:-https://api.moonshot.cn/v1}",
        metadata={
            "help": _("The base url of the Moonshot API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:MOONSHOT_API_KEY}",
        metadata={
            "help": _("The API key of the Moonshot API."),
            "tags": "privacy",
        },
    )


async def moonshot_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: MoonshotLLMClient = cast(MoonshotLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class MoonshotLLMClient(OpenAILLMClient):
    """Moonshot LLM Client.

    Moonshot's API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _MOONSHOT_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _MOONSHOT_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("MOONSHOT_API_BASE") or "https://api.moonshot.cn/v1"
        )
        api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        model = model or _MOONSHOT_DEFAULT_MODEL
        if not context_length:
            if "128k" in model:
                context_length = 1024 * 128
            elif "32k" in model:
                context_length = 1024 * 32
            else:
                # 8k
                context_length = 1024 * 8

        if not api_key:
            raise ValueError(
                "Moonshot API key is required, please set 'MOONSHOT_API_KEY' in "
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

    def check_sdk_version(self, version: str) -> None:
        if not version >= "1.0":
            raise ValueError(
                "Moonshot API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _MOONSHOT_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[MoonshotDeployModelParameters]:
        return MoonshotDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return moonshot_generate_stream


register_proxy_model_adapter(
    MoonshotLLMClient,
    supported_models=[
        ModelMetadata(
            model=["moonshot-v1-8k"],
            context_length=8 * 1024,
            description="Moonshot v1 8k model",
            link="https://platform.moonshot.cn/docs/pricing/chat#%E8%AE%A1%E8%B4%B9%E5%9F%BA%E6%9C%AC%E6%A6%82%E5%BF%B5",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model=["moonshot-v1-32k"],
            context_length=32 * 1024,
            description="Moonshot v1 32k model",
            link="https://platform.moonshot.cn/docs/pricing/chat#%E8%AE%A1%E8%B4%B9%E5%9F%BA%E6%9C%AC%E6%A6%82%E5%BF%B5",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model=["moonshot-v1-32k"],
            context_length=32 * 1024,
            description="Moonshot v1 32k model",
            link="https://platform.moonshot.cn/docs/pricing/chat#%E8%AE%A1%E8%B4%B9%E5%9F%BA%E6%9C%AC%E6%A6%82%E5%BF%B5",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model=["moonshot-v1-128k"],
            context_length=128 * 1024,
            description="Moonshot v1 32k model",
            link="https://platform.moonshot.cn/docs/pricing/chat#%E8%AE%A1%E8%B4%B9%E5%9F%BA%E6%9C%AC%E6%A6%82%E5%BF%B5",  # noqa
            function_calling=True,
        ),
    ],
)
