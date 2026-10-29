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


_RUNCRATE_DEFAULT_API_BASE = "https://api.runcrate.ai/v1"
_RUNCRATE_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"


@auto_register_resource(
    label=_("Runcrate Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Runcrate proxy LLM configuration."),
    documentation_url="https://www.runcrate.ai/inference/pricing",
    show_in_ui=False,
)
@dataclass
class RuncrateDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Runcrate."""

    provider: str = "proxy/runcrate"

    api_base: Optional[str] = field(
        default="${env:RUNCRATE_API_BASE:-https://api.runcrate.ai/v1}",
        metadata={"help": _("The base url of the Runcrate API.")},
    )

    api_key: Optional[str] = field(
        default="${env:RUNCRATE_API_KEY}",
        metadata={"help": _("The API key of the Runcrate API."), "tags": "privacy"},
    )


async def runcrate_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: RuncrateLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class RuncrateLLMClient(OpenAILLMClient):
    """Runcrate LLM Client using OpenAI-compatible endpoints.

    Runcrate serves open-weight models (DeepSeek, GLM, Qwen, Kimi, gpt-oss and
    others) behind an OpenAI-compatible endpoint. Model ids keep the
    ``vendor/model`` form, for example ``deepseek-ai/DeepSeek-V4.1-Flash`` or
    ``zai-org/GLM-5.3``. The full list is served at
    ``https://api.runcrate.ai/v1/models``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _RUNCRATE_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = None,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("RUNCRATE_API_BASE") or _RUNCRATE_DEFAULT_API_BASE
        )
        api_key = api_key or os.getenv("RUNCRATE_API_KEY")
        model = model or _RUNCRATE_DEFAULT_MODEL
        model_alias = model_alias or model
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "Runcrate API key is required, please set 'RUNCRATE_API_KEY' "
                "in environment or pass it as an argument."
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
            model = _RUNCRATE_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[RuncrateDeployModelParameters]:
        return RuncrateDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return runcrate_generate_stream


register_proxy_model_adapter(
    RuncrateLLMClient,
    supported_models=[
        ModelMetadata(
            model=["deepseek-ai/DeepSeek-V4.1-Flash"],
            context_length=1_048_576,
            max_output_length=1_048_576,
            description="DeepSeek V4.1 Flash via Runcrate",
            link="https://www.runcrate.ai/inference/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["zai-org/GLM-5.3", "zai-org/GLM-5.3-Flash"],
            context_length=1_048_576,
            max_output_length=1_048_576,
            description="Zhipu GLM 5.3 models via Runcrate",
            link="https://www.runcrate.ai/inference/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["Qwen/Qwen3.8-Flash"],
            context_length=1_000_000,
            max_output_length=1_000_000,
            description="Qwen3.8 Flash via Runcrate",
            link="https://www.runcrate.ai/inference/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["moonshotai/Kimi-K2.6"],
            context_length=262_144,
            max_output_length=16_384,
            description="Kimi K2.6 via Runcrate",
            link="https://www.runcrate.ai/inference/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["openai/gpt-oss-120b"],
            context_length=131_072,
            max_output_length=117_964,
            description="OpenAI gpt-oss 120B via Runcrate",
            link="https://www.runcrate.ai/inference/pricing",
            function_calling=True,
        ),
    ],
)
