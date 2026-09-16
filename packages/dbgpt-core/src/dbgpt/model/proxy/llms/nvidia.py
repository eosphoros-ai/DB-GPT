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

_DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"


@auto_register_resource(
    label=_("NVIDIA Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("NVIDIA NIM proxy LLM configuration."),
    documentation_url="https://build.nvidia.com/docs/api",
    show_in_ui=False,
)
@dataclass
class NvidiaDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for NVIDIA NIM API."""

    provider: str = "proxy/nvidia"

    api_base: Optional[str] = field(
        default="${env:NVIDIA_API_BASE:-https://integrate.api.nvidia.com/v1}",
        metadata={
            "help": _("The base url of the NVIDIA NIM API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:NVIDIA_API_KEY}",
        metadata={
            "help": _("The API key of the NVIDIA NIM API."),
            "tags": "privacy",
        },
    )


async def nvidia_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: NvidiaLLMClient = cast(NvidiaLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class NvidiaLLMClient(OpenAILLMClient):
    """NVIDIA NIM LLM Client.

    NVIDIA NIM API is compatible with OpenAI's API, so we inherit from
    OpenAILLMClient.

    API Reference: https://build.nvidia.com/docs/api
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
            api_base
            or os.getenv("NVIDIA_API_BASE")
            or "https://integrate.api.nvidia.com/v1"
        )
        api_key = api_key or os.getenv("NVIDIA_API_KEY")
        model = model or _DEFAULT_MODEL
        if not context_length:
            context_length = _infer_context_length(model)

        if not api_key:
            raise ValueError(
                "NVIDIA API key is required, please set 'NVIDIA_API_KEY' in "
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
                "NVIDIA NIM API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[NvidiaDeployModelParameters]:
        """Get the deploy model parameters class."""
        return NvidiaDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return nvidia_generate_stream


def _infer_context_length(model: str) -> int:
    """Infer context length from model name."""
    lower = model.lower()
    # MiniMax M2.7 — 1M context
    if "minimax" in lower and "m2" in lower:
        return 1024 * 1024
    # Llama 3.1 models — 128K
    if "llama-3.1" in lower or "llama3.1" in lower:
        return 128 * 1024
    # Llama 3.3 — 128K
    if "llama-3.3" in lower or "llama3.3" in lower:
        return 128 * 1024
    # Qwen 2.5 — 32K–128K depending on variant
    if "qwen2.5" in lower or "qwen-2.5" in lower:
        return 32 * 1024
    # Mistral / Mixtral — 32K
    if "mistral" in lower or "mixtral" in lower:
        return 32 * 1024
    # DeepSeek models — 64K
    if "deepseek" in lower:
        return 64 * 1024
    # Gemma — 8K
    if "gemma" in lower:
        return 8 * 1024
    # Default fallback
    return 8 * 1024


register_proxy_model_adapter(
    NvidiaLLMClient,
    supported_models=[
        ModelMetadata(
            model="meta/llama-3.1-70b-instruct",
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="Llama 3.1 70B Instruct by Meta",
            link="https://build.nvidia.com/meta/llama-3_1-70b-instruct",
            function_calling=True,
        ),
        ModelMetadata(
            model="meta/llama-3.1-8b-instruct",
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="Llama 3.1 8B Instruct by Meta",
            link="https://build.nvidia.com/meta/llama-3_1-8b-instruct",
            function_calling=True,
        ),
        ModelMetadata(
            model="meta/llama-3.3-70b-instruct",
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="Llama 3.3 70B Instruct by Meta",
            link="https://build.nvidia.com/meta/llama-3_3-70b-instruct",
            function_calling=True,
        ),
        ModelMetadata(
            model="minimaxai/minimax-m2.7",
            context_length=1024 * 1024,
            max_output_length=8 * 1024,
            description="MiniMax M2.7 by MiniMax",
            link="https://build.nvidia.com/minimaxai/minimax-m2-7",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "mistralai/mistral-large-2-instruct",
                "mistralai/mixtral-8x7b-instruct-v0.1",
            ],
            context_length=32 * 1024,
            max_output_length=4 * 1024,
            description="Mistral / Mixtral by Mistral AI",
            link="https://build.nvidia.com/mistralai",
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-ai/deepseek-r1",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 via NVIDIA NIM",
            link="https://build.nvidia.com/deepseek-ai/deepseek-r1",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen/qwen2.5-72b-instruct",
                "qwen/qwen2.5-32b-instruct",
                "qwen/qwen2.5-coder-32b-instruct",
            ],
            context_length=32 * 1024,
            max_output_length=8 * 1024,
            description="Qwen 2.5 by Alibaba",
            link="https://build.nvidia.com/qwen",
            function_calling=True,
        ),
        # More models at: https://build.nvidia.com/explore/discover
    ],
)
