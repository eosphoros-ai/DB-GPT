import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

from dbgpt.core import ModelMetadata
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
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


_DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen-max-latest"


@auto_register_resource(
    label=_("Tongyi Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Tongyi proxy LLM configuration."),
    documentation_url="https://help.aliyun.com/zh/model-studio/getting-started/first-api-call-to-qwen",
    show_in_ui=False,
)
@dataclass
class TongyiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Tongyi."""

    provider: str = "proxy/tongyi"

    api_base: Optional[str] = field(
        default=_DEFAULT_API_BASE,
        metadata={
            "help": _("The base url of the tongyi API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:DASHSCOPE_API_KEY}",
        metadata={
            "help": _("The API key of the tongyi API."),
            "tags": "privacy",
        },
    )


async def tongyi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: TongyiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class TongyiLLMClient(OpenAILLMClient):
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
        api_base = api_base or os.getenv("DASHSCOPE_API_BASE") or _DEFAULT_API_BASE
        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        model = model or _DEFAULT_MODEL
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
                "Tongyi API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[TongyiDeployModelParameters]:
        """Get the deploy model parameters class."""
        return TongyiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return tongyi_generate_stream


register_proxy_model_adapter(
    TongyiLLMClient,
    supported_models=[
        ModelMetadata(
            model=["qwen-max-latest", "qwen-max-2025-01-25", "qwen-max"],
            context_length=32 * 1024,
            description="Qwen Max by Qwen",
            link="https://bailian.console.aliyun.com/#/model-market/detail/qwen-max-latest",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-r1",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://bailian.console.aliyun.com/#/model-market/detail/deepseek-r1",
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-v3",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://bailian.console.aliyun.com/#/model-market/detail/deepseek-v3",
            function_calling=True,
        ),
        # More models see: https://bailian.console.aliyun.com/#/model-market
    ],
)
