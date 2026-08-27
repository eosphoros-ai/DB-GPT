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

SYNTHORAI_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_SYNTHORAI_DEFAULT_MODEL = "claude-opus-5"


@auto_register_resource(
    label=_("Synthorai Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Synthorai proxy LLM configuration."),
    documentation_url="https://synthorai.io/docs/",
    show_in_ui=False,
)
@dataclass
class SynthoraiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Synthorai."""

    provider: str = "proxy/synthorai"

    api_base: Optional[str] = field(
        default="${env:SYNTHORAI_API_BASE:-https://synthorai.io/v1}",
        metadata={"help": _("The base url of the Synthorai API.")},
    )

    api_key: Optional[str] = field(
        default="${env:SYNTHORAI_API_KEY}",
        metadata={"help": _("The API key of the Synthorai API."), "tags": "privacy"},
    )


async def synthorai_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: SynthoraiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class SynthoraiLLMClient(OpenAILLMClient):
    """Synthorai LLM Client using OpenAI-compatible endpoints.

    Synthorai is an LLM gateway that serves models from Anthropic, OpenAI,
    Google, DeepSeek, Qwen, Moonshot, Z.ai and others behind one OpenAI
    compatible endpoint and one API key. Unlike most gateways the model ids are
    bare rather than prefixed with the upstream vendor, for example
    ``claude-opus-5``, ``gpt-5.6-sol`` or ``deepseek-v4-pro``; the live list is
    at https://synthorai.io/models/.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _SYNTHORAI_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _SYNTHORAI_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("SYNTHORAI_API_BASE") or "https://synthorai.io/v1"
        )
        api_key = api_key or os.getenv("SYNTHORAI_API_KEY")
        model = model or _SYNTHORAI_DEFAULT_MODEL
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "Synthorai API key is required, please set 'SYNTHORAI_API_KEY' "
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
        try:
            self.client.default_headers.update(SYNTHORAI_HEADERS)
        except Exception:
            pass

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _SYNTHORAI_DEFAULT_MODEL
        return model

    @classmethod
    def param_class(cls) -> Type[SynthoraiDeployModelParameters]:
        return SynthoraiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return synthorai_generate_stream


# Grouped by (family, context, output) rather than by family. Families do not
# share limits - Claude spans 200K and 1M context, DeepSeek's output ranges from
# 8192 to 393216 - so collapsing a family onto one limit would misstate it for
# part of the group, and these numbers are reported as fact. Generated from
# https://synthorai.io/api/models; every chat model there carries real limits.
register_proxy_model_adapter(
    SynthoraiLLMClient,
    supported_models=[
        ModelMetadata(
            model=[
                "ByteDance-Seed-1.8",
                "Dola-Seed-2.0-lite",
                "Dola-Seed-2.0-mini",
                "Dola-Seed-2.0-pro",
            ],
            context_length=262144,
            max_output_length=4096,
            description="ByteDance Seed models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-fable-5",
            ],
            context_length=200000,
            max_output_length=4096,
            description="Anthropic Claude models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-haiku-4-5",
                "claude-opus-4-5",
                "claude-sonnet-4",
                "claude-sonnet-4-5",
            ],
            context_length=200000,
            max_output_length=64000,
            description="Anthropic Claude models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-opus-4-6",
                "claude-opus-4-7",
                "claude-opus-4-8",
                "claude-opus-5",
                "claude-sonnet-5",
            ],
            context_length=1000000,
            max_output_length=128000,
            description="Anthropic Claude models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "claude-sonnet-4-6",
            ],
            context_length=1000000,
            max_output_length=64000,
            description="Anthropic Claude models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek-3.2",
            ],
            context_length=128000,
            max_output_length=64000,
            description="DeepSeek models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek-v4-flash",
            ],
            context_length=1000000,
            max_output_length=8192,
            description="DeepSeek models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "deepseek-v4-flash-0731",
                "deepseek-v4-pro",
                "deepseek-v4-pro-0813",
            ],
            context_length=1000000,
            max_output_length=393216,
            description="DeepSeek models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-2.5-pro",
                "gemini-3-flash-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
            ],
            context_length=1048576,
            max_output_length=65536,
            description="Google Gemini models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "glm-5",
            ],
            context_length=200000,
            max_output_length=131072,
            description="Z.ai GLM models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "glm-5.2",
            ],
            context_length=1048576,
            max_output_length=131072,
            description="Z.ai GLM models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-5.2",
                "gpt-5.3-codex",
                "gpt-5.4-mini",
                "gpt-5.4-nano",
            ],
            context_length=400000,
            max_output_length=128000,
            description="OpenAI GPT models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-5.4",
                "gpt-5.4-pro",
            ],
            context_length=922000,
            max_output_length=128000,
            description="OpenAI GPT models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-5.5",
                "gpt-5.5-pro",
                "gpt-5.6",
                "gpt-5.6-luna",
                "gpt-5.6-sol",
                "gpt-5.6-terra",
            ],
            context_length=1050000,
            max_output_length=128000,
            description="OpenAI GPT models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "hunyuan-3",
            ],
            context_length=262144,
            max_output_length=128000,
            description="Tencent Hunyuan models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "kimi-k2.5",
            ],
            context_length=262144,
            max_output_length=32768,
            description="Moonshot Kimi models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "kimi-k2.7-code",
            ],
            context_length=256000,
            max_output_length=131072,
            description="Moonshot Kimi models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "kimi-k3",
            ],
            context_length=1000000,
            max_output_length=131072,
            description="Moonshot Kimi models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "minimax-m2.1",
                "minimax-m2.5",
            ],
            context_length=204800,
            max_output_length=64000,
            description="MiniMax models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen3-coder-next",
            ],
            context_length=262144,
            max_output_length=64000,
            description="Qwen models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen3-max",
                "qwen3-vl-flash",
                "qwen3-vl-plus",
            ],
            context_length=256000,
            max_output_length=16384,
            description="Qwen models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen3.5-flash",
                "qwen3.5-plus",
            ],
            context_length=1048576,
            max_output_length=16384,
            description="Qwen models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen3.6-flash",
            ],
            context_length=256000,
            max_output_length=32768,
            description="Qwen models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen3.7-max",
                "qwen3.7-plus",
            ],
            context_length=1000000,
            max_output_length=65536,
            description="Qwen models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "qwen3.8-max",
            ],
            context_length=983616,
            max_output_length=131072,
            description="Qwen models via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
    ],
)
