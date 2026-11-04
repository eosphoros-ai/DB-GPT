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


_ATLASCLOUD_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3.1-Terminus"


@auto_register_resource(
    label=_("Atlas Cloud Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Atlas Cloud proxy LLM configuration."),
    documentation_url="https://atlascloud.ai/docs",
    show_in_ui=False,
)
@dataclass
class AtlasCloudDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Atlas Cloud."""

    provider: str = "proxy/atlascloud"

    api_base: Optional[str] = field(
        default="${env:ATLASCLOUD_API_BASE:-https://api.atlascloud.ai/v1}",
        metadata={"help": _("The base url of the Atlas Cloud API.")},
    )

    api_key: Optional[str] = field(
        default="${env:ATLASCLOUD_API_KEY}",
        metadata={"help": _("The API key of the Atlas Cloud API."), "tags": "privacy"},
    )


async def atlascloud_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: AtlasCloudLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class AtlasCloudLLMClient(OpenAILLMClient):
    """Atlas Cloud LLM Client using OpenAI-compatible endpoints.

    Atlas Cloud serves models from DeepSeek, Qwen, Moonshot, Z.AI, Anthropic,
    OpenAI and others behind a single OpenAI-compatible endpoint and API key.
    Model ids keep their vendor prefix, for example
    ``deepseek-ai/DeepSeek-V3.1-Terminus``, ``zai-org/glm-4.7`` or
    ``moonshotai/kimi-k2.6``.
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
                "Atlas Cloud API key is required, please set 'ATLASCLOUD_API_KEY' "
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


# Context and output lengths below are the values the gateway's public catalog
# (GET https://api.atlascloud.ai/v1/models) reports for each model, read
# 2026-10-05. `function_calling` mirrors whether the catalog lists `tools` in
# the model's supported features.
register_proxy_model_adapter(
    AtlasCloudLLMClient,
    supported_models=[
        ModelMetadata(
            model=["deepseek-ai/DeepSeek-V3.1", "deepseek-ai/DeepSeek-V3.1-Terminus"],
            context_length=131_072,
            max_output_length=65_536,
            description="DeepSeek V3.1 models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek-ai/DeepSeek-V3.2-Exp", "deepseek-ai/deepseek-v3.2"],
            context_length=163_840,
            max_output_length=163_840,
            description="DeepSeek V3.2 models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek-ai/deepseek-v4-flash",
                "deepseek-ai/deepseek-v4-pro",
            ],
            context_length=1_048_576,
            max_output_length=393_216,
            description="DeepSeek V4 models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["Qwen/Qwen3-235B-A22B-Instruct-2507"],
            context_length=131_072,
            max_output_length=131_072,
            description="Qwen3 models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "moonshotai/kimi-k2.5",
                "moonshotai/kimi-k2.6",
                "moonshotai/kimi-k2.7-code",
            ],
            context_length=262_144,
            max_output_length=262_144,
            description="Moonshot Kimi K2 models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["moonshotai/kimi-k3"],
            context_length=1_048_576,
            max_output_length=1_048_576,
            description="Moonshot Kimi K3 served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["zai-org/GLM-4.6", "zai-org/glm-4.7", "zai-org/glm-5"],
            context_length=202_752,
            max_output_length=202_752,
            description="Z.AI GLM models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
        ModelMetadata(
            model=["zai-org/glm-5.2", "zai-org/glm-5.3", "zai-org/glm-5.3-flash"],
            context_length=1_048_576,
            max_output_length=131_072,
            description="Z.AI GLM 5.x models served by Atlas Cloud",
            link="https://atlascloud.ai/models",
            function_calling=True,
        ),
    ],
)
