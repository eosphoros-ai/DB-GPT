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

_YI_DEFAULT_MODEL = "yi-lightning"


@auto_register_resource(
    label=_("Yi Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Yi proxy LLM configuration."),
    documentation_url="https://platform.lingyiwanwu.com/docs",
    show_in_ui=False,
)
@dataclass
class YiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Yi."""

    provider: str = "proxy/yi"

    api_base: Optional[str] = field(
        default="${env:YI_API_BASE:-https://api.lingyiwanwu.com/v1}",
        metadata={
            "help": _("The base url of the Yi API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:YI_API_KEY}",
        metadata={
            "help": _("The API key of the Yi API."),
            "tags": "privacy",
        },
    )


async def yi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: YiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class YiLLMClient(OpenAILLMClient):
    """Yi LLM Client.

    Yi' API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _YI_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _YI_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("YI_API_BASE") or "https://api.lingyiwanwu.com/v1"
        )
        api_key = api_key or os.getenv("YI_API_KEY")
        model = model or _YI_DEFAULT_MODEL
        if not context_length:
            if "200k" in model:
                context_length = 200 * 1024
            else:
                context_length = 4096

        if not api_key:
            raise ValueError(
                "Yi API key is required, please set 'YI_API_KEY' in environment "
                "variable or pass it to the client."
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
            model = _YI_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[YiDeployModelParameters]:
        return YiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return yi_generate_stream


register_proxy_model_adapter(
    YiLLMClient,
    supported_models=[
        ModelMetadata(
            model=["yi-lightning"],
            context_length=16 * 1024,
            description="Yi Lightning by Lingyiwanwu",
            link="https://platform.lingyiwanwu.com/docs",
            function_calling=True,
        ),
    ],
)
