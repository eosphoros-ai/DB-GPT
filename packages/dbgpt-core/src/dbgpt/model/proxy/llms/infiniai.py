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


_INFINIAI_DEFAULT_MODEL = "deepseek-v3"


@auto_register_resource(
    label=_("InfiniAI Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("InfiniAI proxy LLM configuration."),
    documentation_url="https://docs.infini-ai.com/gen-studio/api/tutorial.html",  # noqa
    show_in_ui=False,
)
@dataclass
class InfiniAIDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for InfiniAI."""

    provider: str = "proxy/infiniai"

    api_base: Optional[str] = field(
        default="${env:INFINIAI_API_BASE:-https://cloud.infini-ai.com/maas/v1}",
        metadata={
            "help": _("The base url of the InfiniAI API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:INFINIAI_API_KEY}",
        metadata={
            "help": _("The API key of the InfiniAI API."),
            "tags": "privacy",
        },
    )


async def infiniai_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: InfiniAILLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class InfiniAILLMClient(OpenAILLMClient):
    """InfiniAI LLM Client.

    InfiniAI's API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _INFINIAI_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _INFINIAI_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("INFINIAI_API_BASE")
            or "https://cloud.infini-ai.com/maas/v1"
        )
        api_key = api_key or os.getenv("INFINIAI_API_KEY")
        model = model or _INFINIAI_DEFAULT_MODEL
        if not context_length:
            if "200k" in model:
                context_length = 200 * 1024
            else:
                context_length = 4096

        if not api_key:
            raise ValueError(
                "InfiniAI API key is required, please set 'INFINIAI_API_KEY' in "
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
            model = _INFINIAI_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[InfiniAIDeployModelParameters]:
        return InfiniAIDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return infiniai_generate_stream


register_proxy_model_adapter(
    InfiniAILLMClient,
    supported_models=[
        ModelMetadata(
            model=["deepseek-v3"],
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V3 by DeepSeek",
            link="https://cloud.infini-ai.com/genstudio/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek-r1"],
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V3 by DeepSeek",
            link="https://cloud.infini-ai.com/genstudio/model",
            function_calling=False,
        ),
        ModelMetadata(
            model=["qwq-32b"],
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="qwq By Qwen",
            link="https://cloud.infini-ai.com/genstudio/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen2.5-72b-instruct",
                "qwen2.5-32b-instruct",
                "qwen2.5-14b-instruct",
                "qwen2.5-7b-instruct",
                "qwen2.5-coder-32b-instruct",
            ],
            context_length=32 * 1024,
            max_output_length=4 * 1024,
            description="Qwen 2.5 By Qwen",
            link="https://cloud.infini-ai.com/genstudio/model",
            function_calling=True,
        ),
        # More models see: https://cloud.infiniai.cn/models
    ],
)
