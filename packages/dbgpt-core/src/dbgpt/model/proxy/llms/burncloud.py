import os
from concurrent.futures import Executor
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

_DEFAULT_MODEL = "claude-sonnet-4-20250514"


@auto_register_resource(
    label=_("BurnCloud Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("BurnCloud proxy LLM configuration."),
    documentation_url="https://ai.burncloud.com/",
    show_in_ui=False,
)
@dataclass
class BurnCloudDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for BurnCloud."""

    provider: str = "proxy/burncloud"

    api_base: Optional[str] = field(
        default="${env:BURNCLOUD_API_BASE:-https://ai.burncloud.com/v1}",
        metadata={
            "help": _("The base url of the BurnCloud API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:BURNCLOUD_API_KEY}",
        metadata={
            "help": _("The API key of the BurnCloud API."),
            "tags": "privacy",
        },
    )


async def burncloud_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: BurnCloudLLMClient = cast(BurnCloudLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class BurnCloudLLMClient(OpenAILLMClient):
    """BurnCloud LLM Client.

    BurnCloud's API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.

    API Reference: https://ai.burncloud.com/v1/chat/completions
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
            api_base or os.getenv("BURNCLOUD_API_BASE") or "https://ai.burncloud.com/v1"
        )
        api_key = api_key or os.getenv("BURNCLOUD_API_KEY")
        model = model or _DEFAULT_MODEL

        # Set context length based on model
        if not context_length:
            if any(
                x in model for x in ["claude-opus-4", "claude-sonnet-4", "gpt-5", "o3"]
            ):
                context_length = 200 * 1024  # 200K
            elif any(
                x in model for x in ["claude-3", "gpt-4", "gemini-2.5", "DeepSeek-V3"]
            ):
                context_length = 128 * 1024  # 128K
            else:
                context_length = 32 * 1024  # Default 32K

        if not api_key:
            raise ValueError(
                "BurnCloud API key is required, please set 'BURNCLOUD_API_KEY' in "
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
                "BurnCloud API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[BurnCloudDeployModelParameters]:
        """Get the deploy model parameters class."""
        return BurnCloudDeployModelParameters

    @classmethod
    def new_client(
        cls,
        model_params: BurnCloudDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "BurnCloudLLMClient":
        """Create a new client with the model parameters."""
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            api_type=model_params.api_type,
            api_version=model_params.api_version,
            model=model_params.real_provider_model_name,
            proxy=model_params.http_proxy,
            model_alias=model_params.real_provider_model_name,
            context_length=max(model_params.context_length or 8192, 8192),
        )

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return burncloud_generate_stream


register_proxy_model_adapter(
    BurnCloudLLMClient,
    supported_models=[
        # Claude models
        ModelMetadata(
            model="claude-opus-4-1-20250805",
            context_length=200 * 1024,
            max_output_length=8 * 1024,
            description="Claude Opus 4.1 by Anthropic via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-sonnet-4-20250514",
            context_length=200 * 1024,
            max_output_length=8 * 1024,
            description="Claude Sonnet 4 by Anthropic via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-opus-4-20250514",
            context_length=200 * 1024,
            max_output_length=8 * 1024,
            description="Claude Opus 4 by Anthropic via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-3-7-sonnet-20250219",
            context_length=200 * 1024,
            max_output_length=8 * 1024,
            description="Claude 3.7 Sonnet by Anthropic via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="claude-3-5-sonnet-20241022",
            context_length=200 * 1024,
            max_output_length=8 * 1024,
            description="Claude 3.5 Sonnet by Anthropic via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        # GPT models
        ModelMetadata(
            model="gpt-5-chat-latest",
            context_length=200 * 1024,
            max_output_length=16 * 1024,
            description="GPT-5 Chat Latest by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-5",
            context_length=200 * 1024,
            max_output_length=16 * 1024,
            description="GPT-5 by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-4.1",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4.1 by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-4.1-mini",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4.1 Mini by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="chatgpt-4o-latest",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="ChatGPT-4o Latest by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-4o-2024-11-20",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4o by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-4o",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4o by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-4o-mini",
            context_length=128 * 1024,
            max_output_length=16 * 1024,
            description="GPT-4o Mini by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gpt-image-1",
            context_length=32 * 1024,
            max_output_length=4 * 1024,
            description="GPT Image Generation Model via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=False,
        ),
        ModelMetadata(
            model="text-embedding-3-large",
            context_length=8 * 1024,
            max_output_length=3072,
            description="Text Embedding 3 Large by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=False,
        ),
        # Reasoning models
        ModelMetadata(
            model="o3",
            context_length=200 * 1024,
            max_output_length=100 * 1024,
            description="o3 Reasoning model by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="o3-mini",
            context_length=128 * 1024,
            max_output_length=65 * 1024,
            description="o3-mini Reasoning model by OpenAI via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        # Gemini models
        ModelMetadata(
            model="gemini-2.5-pro",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="Gemini 2.5 Pro by Google via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-2.5-flash",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="Gemini 2.5 Flash by Google via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-2.5-flash-nothink",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="Gemini 2.5 Flash No Think by Google via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-2.5-pro-search",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="Gemini 2.5 Pro Search by Google via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-2.5-pro-preview-06-05",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="Gemini 2.5 Pro Preview by Google via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        ModelMetadata(
            model="gemini-2.5-pro-preview-05-06",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="Gemini 2.5 Pro Preview by Google via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
        # DeepSeek model
        ModelMetadata(
            model="DeepSeek-V3",
            context_length=128 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek V3 by DeepSeek via BurnCloud",
            link="https://ai.burncloud.com/",
            function_calling=True,
        ),
    ],
)
