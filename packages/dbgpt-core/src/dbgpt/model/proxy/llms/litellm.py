import logging
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Type,
    Union,
    cast,
)

from dbgpt.core import MessageConverter, ModelMetadata, ModelOutput, ModelRequest
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
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from .chatgpt import OpenAICompatibleDeployModelParameters

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "openai/gpt-4o-mini"


@auto_register_resource(
    label=_("LiteLLM AI Gateway"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "LiteLLM as an embedded AI gateway — call 100+ LLM providers (OpenAI, "
        "Anthropic, Vertex AI, Bedrock, Azure, Cohere, Mistral, Groq, Ollama, ...) "
        "through a single client without running a separate proxy server. Specify "
        "the model with a provider prefix, for example "
        "'anthropic/claude-3-5-sonnet-20241022', 'vertex_ai/gemini-1.5-pro', "
        "'bedrock/anthropic.claude-3-haiku-20240307-v1:0', or 'azure/gpt-4o'."
    ),
    documentation_url="https://docs.litellm.ai/docs/providers",
    show_in_ui=False,
)
@dataclass
class LiteLLMDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for the embedded LiteLLM gateway."""

    provider: str = "proxy/litellm"

    api_base: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Optional API base URL. LiteLLM resolves the per-provider endpoint "
                "from the model prefix and provider-specific environment variables; "
                "set this only when calling an OpenAI-compatible custom endpoint."
            ),
        },
    )

    api_key: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Optional API key. LiteLLM resolves provider-specific keys from "
                "environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                "AZURE_API_KEY, GROQ_API_KEY, ...) by default; set this only if "
                "your model requires a single shared key."
            ),
            "tags": "privacy",
        },
    )


async def litellm_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
) -> AsyncIterator[ModelOutput]:
    client: LiteLLMClient = cast(LiteLLMClient, model.proxy_llm_client)
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


class LiteLLMClient(ProxyLLMClient):
    """Embedded LiteLLM AI gateway client.

    Routes every request through ``litellm.acompletion`` (the LiteLLM Python
    SDK), so a single DB-GPT model entry can talk to OpenAI, Anthropic, Vertex
    AI, Bedrock, Azure, Cohere, Mistral, Groq, Ollama, and 90+ other providers
    *without running a separate LiteLLM proxy server*. The model is selected
    via the standard LiteLLM provider-prefixed name (``anthropic/...``,
    ``vertex_ai/...``, etc.) and credentials are resolved from provider-specific
    environment variables (``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``,
    ``AWS_ACCESS_KEY_ID``, ...).

    ``drop_params=True`` is enabled by default so kwargs that some providers
    reject (``frequency_penalty`` / ``presence_penalty`` on Anthropic, Gemini,
    Bedrock; ``response_format`` on Bedrock; etc.) are silently dropped instead
    of raising ``UnsupportedParamsError``. Override via
    ``litellm_kwargs={"drop_params": False}``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = None,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = None,
        context_length: Optional[int] = None,
        litellm_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        try:
            import litellm  # noqa: F401
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: litellm. "
                'Please install it via `pip install "litellm>=1.60,<1.85"`.'
            ) from exc

        if not model:
            model = _DEFAULT_MODEL
        if not model_alias:
            model_alias = model
        if not context_length:
            context_length = 1024 * 8

        # drop_params silently strips kwargs that the destination provider does
        # not support (e.g., presence_penalty on Anthropic). Defaulted on so
        # DB-GPT's generic per-request payload doesn't crash provider-specific
        # backends. Users can opt out via litellm_kwargs={"drop_params": False}.
        merged_kwargs: Dict[str, Any] = {"drop_params": True}
        if litellm_kwargs:
            merged_kwargs.update(litellm_kwargs)

        self._model = model
        self._api_key = self._resolve_env_vars(api_key)
        self._api_base = self._resolve_env_vars(api_base)
        self._api_type = self._resolve_env_vars(api_type)
        self._api_version = self._resolve_env_vars(api_version)
        self._proxies = proxies
        self._timeout = timeout
        self._model_alias = model_alias
        self._context_length = context_length
        self._litellm_kwargs = merged_kwargs

        super().__init__(model_names=[model_alias], context_length=context_length)

    @classmethod
    def param_class(cls) -> Type[LiteLLMDeployModelParameters]:
        """Get the deploy model parameters class."""
        return LiteLLMDeployModelParameters

    @classmethod
    def new_client(
        cls,
        model_params: LiteLLMDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "LiteLLMClient":
        """Create a new client with the deploy model parameters."""
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            api_type=model_params.api_type,
            api_version=model_params.api_version,
            model=model_params.real_provider_model_name,
            proxies=model_params.http_proxy,
            model_alias=model_params.real_provider_model_name,
            context_length=max(model_params.context_length or 8192, 8192),
        )

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return litellm_generate_stream

    @property
    def default_model(self) -> str:
        return self._model or _DEFAULT_MODEL

    def _build_request(
        self, request: ModelRequest, stream: Optional[bool] = False
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"stream": stream}
        payload["model"] = request.model or self.default_model
        # Provider-specific overrides come last so users can shadow defaults.
        for k, v in self._litellm_kwargs.items():
            payload[k] = v
        if self._api_key:
            payload["api_key"] = self._api_key
        if self._api_base:
            payload["api_base"] = self._api_base
        if self._api_version:
            payload["api_version"] = self._api_version
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_new_tokens:
            payload["max_tokens"] = request.max_new_tokens
        if request.stop:
            payload["stop"] = request.stop
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if self._timeout:
            payload.setdefault("timeout", self._timeout)
        if stream:
            # Ask LiteLLM/OpenAI for a final usage chunk so we can report tokens.
            payload.setdefault("stream_options", {"include_usage": True})
        return payload

    async def generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        import litellm

        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages()
        payload = self._build_request(request)
        logger.info(
            f"Send request to litellm, payload: {payload}\n\nmessages:\n{messages}"
        )
        try:
            response = await litellm.acompletion(messages=messages, **payload)
            message_obj = response.choices[0].message
            text = message_obj.content
            reasoning_content = getattr(message_obj, "reasoning_content", "") or ""
            usage = response.usage.model_dump() if response.usage else None
            return ModelOutput.build(text, reasoning_content, usage=usage)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )

    async def generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> AsyncIterator[ModelOutput]:
        import litellm

        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages()
        payload = self._build_request(request, stream=True)
        logger.info(
            f"Send request to litellm (stream), payload: {payload}\n\n"
            f"messages:\n{messages}"
        )
        try:
            response = await litellm.acompletion(messages=messages, **payload)
            text = ""
            reasoning_content = ""
            usage: Optional[Dict[str, Any]] = None
            async for chunk in response:
                # Some providers (Anthropic, Bedrock via LiteLLM) attach usage on
                # the final content chunk; OpenAI / Azure with
                # stream_options=include_usage emit a trailing usage-only chunk
                # with empty choices. Capture either form.
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage = chunk_usage.model_dump()
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                choice = choices[0]
                if choice is None or choice.delta is None:
                    continue
                delta_obj = choice.delta
                new_reasoning = ""
                if (
                    hasattr(delta_obj, "reasoning_content")
                    and delta_obj.reasoning_content
                ):
                    new_reasoning = delta_obj.reasoning_content
                    reasoning_content += new_reasoning
                new_content = delta_obj.content if delta_obj.content is not None else ""
                if new_content:
                    text += new_content
                # Only yield when this chunk carried new content/reasoning so we
                # don't emit duplicate frames on finish-only chunks.
                if new_content or new_reasoning:
                    yield ModelOutput.build(text, reasoning_content, usage=usage)
        except Exception as e:
            yield ModelOutput(
                text=(
                    f"**LLMServer Generate Stream Error, Please CheckErrorInfo.**: {e}"
                ),
                error_code=1,
            )

    async def models(self) -> List[ModelMetadata]:
        return [
            ModelMetadata(
                model=self._model_alias,
                context_length=await self.get_context_length(),
            )
        ]

    async def get_context_length(self) -> int:
        return self._context_length


register_proxy_model_adapter(
    LiteLLMClient,
    supported_models=[
        ModelMetadata(
            model=[
                "openai/gpt-4o",
                "openai/gpt-4o-mini",
                "openai/gpt-4-turbo",
                "openai/o1",
                "openai/o1-mini",
                "openai/o3-mini",
            ],
            context_length=128000,
            max_output_length=16384,
            description="OpenAI models routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/openai",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "anthropic/claude-3-5-sonnet-20241022",
                "anthropic/claude-3-5-sonnet-latest",
                "anthropic/claude-3-5-haiku-latest",
                "anthropic/claude-3-opus-latest",
                "anthropic/claude-3-haiku-20240307",
            ],
            context_length=200000,
            max_output_length=8192,
            description="Anthropic Claude routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/anthropic",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "vertex_ai/gemini-1.5-pro",
                "vertex_ai/gemini-1.5-flash",
                "vertex_ai/gemini-2.0-flash",
            ],
            context_length=1048576,
            max_output_length=8192,
            description="Google Vertex AI Gemini routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/vertex",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
                "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
            ],
            context_length=200000,
            max_output_length=8192,
            description="AWS Bedrock Anthropic Claude routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/bedrock",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "azure/gpt-4o",
                "azure/gpt-4o-mini",
            ],
            context_length=128000,
            max_output_length=16384,
            description="Azure OpenAI routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/azure",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "groq/llama-3.3-70b-versatile",
                "groq/llama-3.1-70b-versatile",
                "groq/mixtral-8x7b-32768",
            ],
            context_length=131072,
            max_output_length=8192,
            description="Groq routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/groq",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "mistral/mistral-large-latest",
                "mistral/mistral-small-latest",
            ],
            context_length=131072,
            max_output_length=8192,
            description="Mistral routed via LiteLLM",
            link="https://docs.litellm.ai/docs/providers/mistral",
            function_calling=True,
        ),
    ],
)
