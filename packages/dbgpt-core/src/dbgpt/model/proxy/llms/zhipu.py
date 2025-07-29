import logging
import os
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

from dbgpt.core import ModelMetadata
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.util.i18n_utils import _

from .chatgpt import OpenAICompatibleDeployModelParameters, OpenAILLMClient

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "glm-4.5"


@auto_register_resource(
    label=_("Zhipu Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Zhipu proxy LLM configuration."),
    documentation_url="https://docs.bigmodel.cn/cn/guide/start/model-overview",
    show_in_ui=False,
)
@dataclass
class ZhipuDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Zhipu."""

    provider: str = "proxy/zhipu"

    api_base: Optional[str] = field(
        default="${env:ZHIPUAI_BASE_URL:-https://open.bigmodel.cn/api/paas/v4}",
        metadata={
            "help": _("The base url of the Zhipu API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:ZHIPUAI_API_KEY}",
        metadata={
            "help": _("The API key of the Zhipu API."),
            "tags": "privacy",
        },
    )


async def zhipu_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://docs.bigmodel.cn/cn/guide/start/model-overview"""
    client: ZhipuLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class ZhipuLLMClient(OpenAILLMClient):
    def __init__(
        self,
        model: Optional[str] = _DEFAULT_MODEL,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        proxies: Optional["ProxiesTypes"] = None,
        model_alias: Optional[str] = _DEFAULT_MODEL,
        timeout: Optional[int] = 240,
        context_length: Optional[int] = 8192,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        if not model:
            model = _DEFAULT_MODEL
        if not api_key:
            # Compatible with DB-GPT's config
            api_key = os.getenv("ZHIPU_PROXY_API_KEY")

        api_key = self._resolve_env_vars(api_key)
        api_base = self._resolve_env_vars(api_base)
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

    @classmethod
    def new_client(
        cls,
        model_params: ZhipuDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "ZhipuLLMClient":
        return cls(
            model=model_params.real_provider_model_name,
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
            executor=default_executor,
        )

    @classmethod
    def param_class(cls) -> Type[LLMDeployModelParameters]:
        return ZhipuDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return zhipu_generate_stream

    @property
    def default_model(self) -> str:
        return _DEFAULT_MODEL


register_proxy_model_adapter(
    ZhipuLLMClient,
    supported_models=[
        ModelMetadata(
            model=["glm-4.5", "glm-4.5-air", "glm-4.5-x", "glm-4.5-airx"],
            context_length=128 * 1024,
            max_output_length=96 * 1024,
            description="GLM-4.5 by Zhipu AI",
            link="https://docs.bigmodel.cn/cn/guide/start/model-overview",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-plus", "glm-4-air", "glm-4-air-0111"],
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="GLM-4 by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-long"],
            context_length=1000 * 1024,
            max_output_length=4 * 1024,
            description="Long context GLM-4 by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-flash", "glm-4-flashx"],
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="Flash version of GLM-4 by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-airx"],
            context_length=8 * 1024,
            max_output_length=4 * 1024,
            description="Quick response reasoning model by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-zero-preview"],
            context_length=16 * 1024,
            max_output_length=12 * 1024,
            description="Reasoning model by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
    ],
)
