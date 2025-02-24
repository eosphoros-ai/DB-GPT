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


_GITEE_DEFAULT_MODEL = "Qwen2.5-72B-Instruct"


@auto_register_resource(
    label=_("Gitee Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Gitee proxy LLM configuration."),
    documentation_url="https://ai.gitee.com/docs/getting-started/intro",
    show_in_ui=False,
)
@dataclass
class GiteeDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for DeepSeek."""

    provider: str = "proxy/gitee"

    api_base: Optional[str] = field(
        default="${env:GITEE_API_BASE:-https://ai.gitee.com/v1}",
        metadata={
            "help": _("The base url of the Gitee API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:GITEE_API_KEY}",
        metadata={
            "help": _("The API key of the Gitee API."),
            "tags": "privacy",
        },
    )


async def gitee_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: GiteeLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class GiteeLLMClient(OpenAILLMClient):
    """Gitee LLM Client.

    Gitee's API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _GITEE_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _GITEE_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = api_base or os.getenv("GITEE_API_BASE") or "https://ai.gitee.com/v1"
        api_key = api_key or os.getenv("GITEE_API_KEY")
        model = model or _GITEE_DEFAULT_MODEL
        if not context_length:
            if "200k" in model:
                context_length = 200 * 1024
            else:
                context_length = 4096

        if not api_key:
            raise ValueError(
                "Gitee API key is required, please set 'GITEE_API_KEY' in environment "
                "or pass it as an argument."
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
            model = _GITEE_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[GiteeDeployModelParameters]:
        return GiteeDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return gitee_generate_stream


register_proxy_model_adapter(
    GiteeLLMClient,
    supported_models=[
        ModelMetadata(
            model="DeepSeek-V3",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-V3 by DeepSeek",
            link="https://ai.gitee.com/hf-models/deepseek-ai/DeepSeek-V3/api",
            function_calling=True,
        ),
        ModelMetadata(
            model="DeepSeek-R1",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://ai.gitee.com/hf-models/deepseek-ai/DeepSeek-R1/api",
            function_calling=True,
        ),
        # More models see: https://ai.gitee.com/models
    ],
)
