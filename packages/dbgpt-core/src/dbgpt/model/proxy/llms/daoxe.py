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

DAOXE_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]


_DAOXE_DEFAULT_MODEL = "claude-sonnet-4-6"


@auto_register_resource(
    label=_("DaoXE Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("DaoXE proxy LLM configuration."),
    documentation_url="https://daoxe.com/docs/",
    show_in_ui=False,
)
@dataclass
class DaoxeDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for DaoXE."""

    provider: str = "proxy/daoxe"

    api_base: Optional[str] = field(
        default="${env:DAOXE_API_BASE:-https://api.daoxe.com/v1}",
        metadata={"help": _("The base url of the DaoXE API.")},
    )

    api_key: Optional[str] = field(
        default="${env:DAOXE_API_KEY}",
        metadata={"help": _("The API key of the DaoXE API."), "tags": "privacy"},
    )


async def daoxe_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: DaoxeLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class DaoxeLLMClient(OpenAILLMClient):
    """DaoXE LLM Client using OpenAI-compatible endpoints.

    DaoXE is a multi-model LLM gateway that serves models from Anthropic,
    OpenAI, Google, DeepSeek, Qwen, Moonshot, Z.ai, xAI and others behind one
    OpenAI-compatible endpoint and one API key. Model ids are bare rather than
    prefixed with the upstream vendor, for example ``claude-opus-4-8``,
    ``gpt-5.4`` or ``deepseek-v4-pro``; the live catalog is at
    https://daoxe.com/pricing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _DAOXE_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = _DAOXE_DEFAULT_MODEL,
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = api_base or os.getenv("DAOXE_API_BASE") or "https://api.daoxe.com/v1"
        api_key = api_key or os.getenv("DAOXE_API_KEY")
        model = model or _DAOXE_DEFAULT_MODEL
        if not context_length:
            context_length = 128 * 1024

        if not api_key:
            raise ValueError(
                "DaoXE API key is required, please set 'DAOXE_API_KEY' "
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
        default_headers = getattr(self.client, "default_headers", None)
        if default_headers is not None:
            default_headers.update(DAOXE_HEADERS)

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DAOXE_DEFAULT_MODEL
        return model

    @classmethod
    def new_client(
        cls,
        model_params: DaoxeDeployModelParameters,
        default_executor=None,
    ) -> "DaoxeLLMClient":
        """Create a new client with the model parameters.

        Overridden to pass ``context_length`` through untouched. The inherited
        version clamps it with ``max(model_params.context_length or 8192, 8192)``,
        so an unset window arrives as 8192 rather than ``None`` and the
        constructor's own 128K default below stops applying - the client then
        reports 8192 for a model whose ``supported_models()`` entry advertises
        200K-1M. ``DeepseekLLMClient.new_client`` overrides it for the same
        reason, passing ``model_params.context_length`` straight through.
        """
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            api_type=model_params.api_type,
            api_version=model_params.api_version,
            model=model_params.real_provider_model_name,
            proxy=model_params.http_proxy,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
        )

    @classmethod
    def param_class(cls) -> Type[DaoxeDeployModelParameters]:
        return DaoxeDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return daoxe_generate_stream


# supported_models() reports context/output limits as fact, so only models
# whose per-model limits are published in DaoXE's own catalog index are listed
# here (https://models.dev/providers/daoxe). DaoXE passes requests through to
# the upstream that enforces those limits; they are not separately measured
# gateway caps. The full catalog is larger - hundreds of models across ~25
# upstream providers - and unlisted ids still route fine by name, reporting no
# window unless one is configured. Families do not share limits (Claude spans
# 200K and 1M context), so each row is one published limit rather than a
# family-wide guess.
register_proxy_model_adapter(
    DaoxeLLMClient,
    supported_models=[
        ModelMetadata(
            model=["claude-haiku-4-5-20251001"],
            context_length=200_000,
            max_output_length=64_000,
            description="Anthropic Claude models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["claude-sonnet-4-6"],
            context_length=1_000_000,
            max_output_length=64_000,
            description="Anthropic Claude models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["claude-opus-4-8"],
            context_length=1_000_000,
            max_output_length=128_000,
            description="Anthropic Claude models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["gpt-5.4", "gpt-5.5"],
            context_length=1_050_000,
            max_output_length=128_000,
            description="OpenAI GPT models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["gemini-3.1-pro-preview"],
            context_length=1_048_576,
            max_output_length=65_536,
            description="Google Gemini models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["grok-4.3"],
            context_length=1_000_000,
            max_output_length=30_000,
            description="xAI Grok models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["grok-4.5"],
            context_length=500_000,
            max_output_length=500_000,
            description="xAI Grok models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
        ModelMetadata(
            model=["kimi-k2.5"],
            context_length=262_144,
            max_output_length=262_144,
            description="Moonshot Kimi models via DaoXE",
            link="https://daoxe.com/pricing",
            function_calling=True,
        ),
    ],
)
