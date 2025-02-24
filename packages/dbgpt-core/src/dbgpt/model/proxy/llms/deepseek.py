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

# 32K model
_DEFAULT_MODEL = "deepseek-chat"


@auto_register_resource(
    label=_("Deepseek Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Deepseek proxy LLM configuration."),
    documentation_url="https://api-docs.deepseek.com/",
    show_in_ui=False,
)
@dataclass
class DeepSeekDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for DeepSeek."""

    provider: str = "proxy/deepseek"

    api_base: Optional[str] = field(
        default="${env:DEEPSEEK_API_BASE:-https://api.deepseek.com/v1}",
        metadata={
            "help": _("The base url of the DeepSeek API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:DEEPSEEK_API_KEY}",
        metadata={
            "help": _("The API key of the DeepSeek API."),
            "tags": "privacy",
        },
    )


async def deepseek_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: DeepseekLLMClient = cast(DeepseekLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class DeepseekLLMClient(OpenAILLMClient):
    """Deepseek LLM Client.

    Deepseek's API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.

    API Reference: https://platform.deepseek.com/api-docs/
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
            api_base or os.getenv("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"
        )
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        model = model or _DEFAULT_MODEL
        if not context_length:
            if "deepseek-chat" in model:
                context_length = 1024 * 32
            elif "deepseek-coder" in model:
                context_length = 1024 * 16
            else:
                # 8k
                context_length = 1024 * 8

        if not api_key:
            raise ValueError(
                "Deepseek API key is required, please set 'DEEPSEEK_API_KEY' in "
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
                "Deepseek API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[DeepSeekDeployModelParameters]:
        """Get the deploy model parameters class."""
        return DeepSeekDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return deepseek_generate_stream


register_proxy_model_adapter(
    DeepseekLLMClient,
    supported_models=[
        ModelMetadata(
            model="deepseek-chat",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V3 by DeepSeek",
            link="https://api-docs.deepseek.com/news/news1226",
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-reasoner",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://api-docs.deepseek.com/news/news250120",
            function_calling=True,
        ),
    ],
)
