import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union, cast

from dbgpt.core import ModelMetadata, ModelRequest
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

_DEFAULT_MODEL = "MiniMax-M2.7"


@auto_register_resource(
    label=_("MiniMax Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("MiniMax proxy LLM configuration."),
    documentation_url="https://platform.minimax.io/docs/api-reference/text-openai-api",
    show_in_ui=False,
)
@dataclass
class MiniMaxDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for MiniMax."""

    provider: str = "proxy/minimax"

    api_base: Optional[str] = field(
        default="${env:MINIMAX_API_BASE:-https://api.minimax.io/v1}",
        metadata={
            "help": _("The base url of the MiniMax API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:MINIMAX_API_KEY}",
        metadata={
            "help": _("The API key of the MiniMax API."),
            "tags": "privacy",
        },
    )


async def minimax_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: MiniMaxLLMClient = cast(MiniMaxLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class MiniMaxLLMClient(OpenAILLMClient):
    """MiniMax LLM Client.

    MiniMax's API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.

    API Reference: https://platform.minimax.io/docs/api-reference/text-openai-api
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
            api_base or os.getenv("MINIMAX_API_BASE") or "https://api.minimax.io/v1"
        )
        api_key = api_key or os.getenv("MINIMAX_API_KEY")
        model = model or _DEFAULT_MODEL
        if not context_length:
            context_length = 204800

        if not api_key:
            raise ValueError(
                "MiniMax API key is required, please set 'MINIMAX_API_KEY' in "
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
                "MiniMax API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _DEFAULT_MODEL
        return model

    def _build_request(
        self, request: ModelRequest, stream: Optional[bool] = False
    ) -> Dict[str, Any]:
        payload = super()._build_request(request, stream)
        # MiniMax requires temperature in (0.0, 1.0]; 0 is not allowed.
        temperature = payload.get("temperature")
        if temperature is not None:
            if temperature <= 0:
                payload["temperature"] = 1.0
            elif temperature > 1.0:
                payload["temperature"] = 1.0
        return payload

    @classmethod
    def param_class(cls) -> Type[MiniMaxDeployModelParameters]:
        """Get the deploy model parameters class."""
        return MiniMaxDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return minimax_generate_stream


register_proxy_model_adapter(
    MiniMaxLLMClient,
    supported_models=[
        ModelMetadata(
            model="MiniMax-M2.7",
            context_length=204800,
            max_output_length=192000,
            description=(
                "MiniMax-M2.7 by MiniMax. Latest flagship model with enhanced "
                "reasoning and coding."
            ),
            link="https://platform.minimax.io/docs/api-reference/text-openai-api",
            function_calling=True,
        ),
        ModelMetadata(
            model="MiniMax-M2.7-highspeed",
            context_length=204800,
            max_output_length=192000,
            description=(
                "MiniMax-M2.7-highspeed by MiniMax. High-speed version of M2.7 "
                "for low-latency scenarios."
            ),
            link="https://platform.minimax.io/docs/api-reference/text-openai-api",
            function_calling=True,
        ),
        ModelMetadata(
            model="MiniMax-M2.5",
            context_length=204800,
            max_output_length=192000,
            description=("MiniMax-M2.5 by MiniMax. Peak Performance. Ultimate Value."),
            link="https://platform.minimax.io/docs/api-reference/text-openai-api",
            function_calling=True,
        ),
        ModelMetadata(
            model="MiniMax-M2.5-highspeed",
            context_length=204800,
            max_output_length=192000,
            description=(
                "MiniMax-M2.5-highspeed by MiniMax. Same performance, faster and "
                "more agile."
            ),
            link="https://platform.minimax.io/docs/api-reference/text-openai-api",
            function_calling=True,
        ),
    ],
)
