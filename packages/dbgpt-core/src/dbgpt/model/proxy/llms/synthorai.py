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


# Only the four models whose context/output limits have been published with
# supporting measurements are enumerated here. The catalog is larger, but
# listing a model without a verified limit would be guessing at a number the
# adapter then reports as fact; anything not listed still routes fine by id.
register_proxy_model_adapter(
    SynthoraiLLMClient,
    supported_models=[
        ModelMetadata(
            model=["claude-opus-5"],
            context_length=1_000_000,
            max_output_length=128_000,
            description="Anthropic Claude Opus 5 via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=["deepseek-v4-pro"],
            context_length=1_000_000,
            max_output_length=384_000,
            description="DeepSeek V4 Pro via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-5.2"],
            context_length=1_000_000,
            max_output_length=131_072,
            description="Z.ai GLM-5.2 via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
        ModelMetadata(
            model=["kimi-k3"],
            context_length=1_048_576,
            max_output_length=131_072,
            description="Moonshot Kimi K3 via Synthorai",
            link="https://synthorai.io/models/",
            function_calling=True,
        ),
    ],
)
