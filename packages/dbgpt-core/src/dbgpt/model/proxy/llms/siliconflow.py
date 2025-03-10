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


_SILICONFLOW_DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"


@auto_register_resource(
    label=_("SiliconFlow Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("SiliconFlow proxy LLM configuration."),
    documentation_url="https://docs.siliconflow.cn/en/api-reference/chat-completions/chat-completions",  # noqa
    show_in_ui=False,
)
@dataclass
class SiliconFlowDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for SiliconFlow."""

    provider: str = "proxy/siliconflow"

    api_base: Optional[str] = field(
        default="${env:SILICONFLOW_API_BASE:-https://api.siliconflow.cn/v1}",
        metadata={
            "help": _("The base url of the SiliconFlow API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:SILICONFLOW_API_KEY}",
        metadata={
            "help": _("The API key of the SiliconFlow API."),
            "tags": "privacy",
        },
    )


async def siliconflow_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: SiliconFlowLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class SiliconFlowLLMClient(OpenAILLMClient):
    """SiliconFlow LLM Client.

    SiliconFlow's API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _SILICONFLOW_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _SILICONFLOW_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base
            or os.getenv("SILICONFLOW_API_BASE")
            or "https://api.siliconflow.cn/v1"
        )
        api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        model = model or _SILICONFLOW_DEFAULT_MODEL
        if not context_length:
            if "200k" in model:
                context_length = 200 * 1024
            else:
                context_length = 4096

        if not api_key:
            raise ValueError(
                "SiliconFlow API key is required, please set 'SILICONFLOW_API_KEY' in "
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
            model = _SILICONFLOW_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[SiliconFlowDeployModelParameters]:
        return SiliconFlowDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return siliconflow_generate_stream


register_proxy_model_adapter(
    SiliconFlowLLMClient,
    supported_models=[
        ModelMetadata(
            model=["deepseek-ai/DeepSeek-V3", "Pro/deepseek-ai/DeepSeek-V3"],
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V3 by DeepSeek",
            link="https://siliconflow.cn/zh-cn/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek-ai/DeepSeek-R1", "Pro/deepseek-ai/DeepSeek-R1"],
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://siliconflow.cn/zh-cn/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "Qwen/Qwen2.5-Coder-32B-Instruct",
                "Qwen/Qwen2.5-72B-Instruct",
                "Qwen/Qwen2.5-32B-Instruct",
                "Qwen/Qwen2.5-14B-Instruct",
                "Qwen/Qwen2.5-7B-Instruct",
                "Qwen/Qwen2.5-Coder-7B-Instruct",
            ],
            context_length=32 * 1024,
            description="Qwen 2.5 By Qwen",
            link="https://siliconflow.cn/zh-cn/models",
            function_calling=True,
        ),
        # More models see: https://cloud.siliconflow.cn/models
    ],
)
