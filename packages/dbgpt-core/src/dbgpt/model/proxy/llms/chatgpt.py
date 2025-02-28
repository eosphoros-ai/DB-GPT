import logging
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Type, Union

from dbgpt.core import MessageConverter, ModelMetadata, ModelOutput, ModelRequest
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    Parameter,
    ResourceCategory,
    auto_register_resource,
    register_resource,
)
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.model.utils.chatgpt_utils import OpenAIParameters
from dbgpt.util.i18n_utils import _

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("OpenAI Compatible Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("OpenAI Compatible Proxy LLM"),
    documentation_url="https://platform.openai.com/docs/api-reference/chat",
    show_in_ui=False,
)
@dataclass
class OpenAICompatibleDeployModelParameters(LLMDeployModelParameters):
    """OpenAI compatible deploy model parameters."""

    provider: str = "proxy/openai"

    api_base: Optional[str] = field(
        default="${env:OPENAI_API_BASE:-https://api.openai.com/v1}",
        metadata={
            "help": _("The base url of the OpenAI API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:OPENAI_API_KEY}",
        metadata={
            "help": _("The API key of the OpenAI API."),
            "tags": "privacy",
        },
    )
    api_type: Optional[str] = field(
        default=None,
        metadata={
            "help": _("The type of the OpenAI API, if you use Azure, it can be: azure")
        },
    )
    api_version: Optional[str] = field(
        default=None,
        metadata={
            "help": _("The version of the OpenAI API."),
        },
    )
    context_length: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "The context length of the OpenAI API. If None, it is determined by the"
                " model."
            )
        },
    )

    http_proxy: Optional[str] = field(
        default=None,
        metadata={"help": _("The http or https proxy to use openai")},
    )

    concurrency: Optional[int] = field(
        default=100, metadata={"help": _("Model concurrency limit")}
    )


async def chatgpt_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: OpenAILLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    async for r in client.generate_stream(request):
        yield r


@register_resource(
    label=_("OpenAI LLM Client"),
    name="openai_llm_client",
    category=ResourceCategory.LLM_CLIENT,
    parameters=[
        Parameter.build_from(
            label=_("OpenAI API Key"),
            name="api_key",
            type=str,
            optional=True,
            default=None,
            description=_(
                "OpenAI API Key, not required if you have set OPENAI_API_KEY "
                "environment variable."
            ),
        ),
        Parameter.build_from(
            label=_("OpenAI API Base"),
            name="api_base",
            type=str,
            optional=True,
            default=None,
            description=_(
                "OpenAI API Base, not required if you have set OPENAI_API_BASE "
                "environment variable."
            ),
        ),
    ],
    documentation_url="https://github.com/openai/openai-python",
)
class OpenAILLMClient(ProxyLLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = None,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = "gpt-4o-mini",
        context_length: Optional[int] = 8192,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        try:
            import openai  # noqa: F401
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: openai "
                "Please install openai by command `pip install openai"
            ) from exc

        self._init_params = OpenAIParameters(
            api_type=self._resolve_env_vars(api_type),
            api_base=self._resolve_env_vars(api_base),
            api_key=self._resolve_env_vars(api_key),
            api_version=self._resolve_env_vars(api_version),
            proxies=proxies,
            full_url=kwargs.get("full_url"),
        )

        self._model = model
        self._proxies = proxies
        self._timeout = timeout
        self._model_alias = model_alias
        self._context_length = context_length
        self._api_type = api_type
        self._client = openai_client
        self._openai_kwargs = openai_kwargs or {}
        super().__init__(model_names=[model_alias], context_length=context_length)

        # Prepare openai client and cache default headers
        # It will block the main thread in some cases
        _ = self.client.default_headers

    @classmethod
    def param_class(cls) -> Type[OpenAICompatibleDeployModelParameters]:
        """Get model parameters class.

        This method will be called by the factory method to get the model parameters
        class.

        Returns:
            Type[OpenAICompatibleDeployModelParameters]: model parameters class

        """
        return OpenAICompatibleDeployModelParameters

    @classmethod
    def new_client(
        cls,
        model_params: OpenAICompatibleDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "OpenAILLMClient":
        """Create a new client with the model parameters."""
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            api_type=model_params.api_type,
            api_version=model_params.api_version,
            model=model_params.real_provider_model_name,
            proxies=model_params.http_proxy,
            model_alias=model_params.real_provider_model_name,
            context_length=max(model_params.context_length or 8192, 8192),
            # full_url=model_params.proxy_server_url,
        )

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get generate stream function.

        Returns:
            Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
                generate stream function
        """
        return chatgpt_generate_stream

    @property
    def client(self) -> "ClientType":
        if self._client is None:
            from dbgpt.model.utils.chatgpt_utils import _build_openai_client

            self._api_type, self._client = _build_openai_client(
                init_params=self._init_params
            )
        return self._client

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = "gpt-35-turbo" if self._api_type == "azure" else "gpt-4o-mini"
        return model

    def _build_request(
        self, request: ModelRequest, stream: Optional[bool] = False
    ) -> Dict[str, Any]:
        payload = {"stream": stream}
        model = request.model or self.default_model
        payload["model"] = model
        # Apply openai kwargs
        for k, v in self._openai_kwargs.items():
            payload[k] = v
        if request.temperature:
            payload["temperature"] = request.temperature
        if request.max_new_tokens:
            payload["max_tokens"] = request.max_new_tokens
        if request.stop:
            payload["stop"] = request.stop
        if request.top_p:
            payload["top_p"] = request.top_p
        return payload

    async def generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages()
        payload = self._build_request(request)
        logger.info(
            f"Send request to openai, payload: {payload}\n\n messages:\n{messages}"
        )
        try:
            return await self.generate_v1(messages, payload)
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
        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages()
        payload = self._build_request(request, stream=True)
        logger.info(
            f"Send request to openai, payload: {payload}\n\n messages:\n{messages}"
        )
        async for r in self.generate_stream_v1(messages, payload):
            yield r

    async def generate_v1(
        self, messages: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> ModelOutput:
        chat_completion = await self.client.chat.completions.create(
            messages=messages, **payload
        )
        reasoning_content = ""
        message_obj = chat_completion.choices[0].message
        if hasattr(message_obj, "reasoning_content"):
            reasoning_content = message_obj.reasoning_content
        text = chat_completion.choices[0].message.content
        usage = chat_completion.usage.dict()
        return ModelOutput.build(text, reasoning_content, usage=usage)

    async def generate_stream_v1(
        self, messages: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> AsyncIterator[ModelOutput]:
        chat_completion = await self.client.chat.completions.create(
            messages=messages, **payload
        )
        text = ""
        reasoning_content = ""
        usage = None
        async for r in chat_completion:
            if len(r.choices) == 0:
                continue
            # Check for empty 'choices' issue in Azure GPT-4o responses
            if r.choices[0] is not None and r.choices[0].delta is None:
                continue
            delta_obj = r.choices[0].delta
            if hasattr(delta_obj, "reasoning_content"):
                reasoning_content += delta_obj.reasoning_content or ""
            if r.choices[0].delta.content is not None:
                text += r.choices[0].delta.content
            if text or reasoning_content:
                if hasattr(r, "usage") and r.usage is not None:
                    usage = r.usage.dict()
                yield ModelOutput.build(text, reasoning_content, usage=usage)

    async def models(self) -> List[ModelMetadata]:
        model_metadata = ModelMetadata(
            model=self._model_alias,
            context_length=await self.get_context_length(),
        )
        return [model_metadata]

    async def get_context_length(self) -> int:
        """Get the context length of the model.

        Returns:
            int: The context length.
        TODO: This is a temporary solution. We should have a better way to get the
        context length.
            eg. get real context length from the openai api.
        """
        return self._context_length


register_proxy_model_adapter(
    OpenAILLMClient,
    supported_models=[
        ModelMetadata(
            model=[
                "gpt-4o",
                "gpt-4o-2024-08-06",
                "gpt-4o-2024-11-20",
                "gpt-4o-2024-08-06",
            ],
            context_length=128000,
            max_output_length=16384,
            description="The flagship model across audio, vision, and text by OpenAI",
            link="https://openai.com/index/hello-gpt-4o/",
            function_calling=True,
        ),
        ModelMetadata(
            model=["gpt-4o-mini", "gpt-4o-mini-2024-07-18", "gpt-4o-mini-2024-07-18"],
            context_length=128000,
            max_output_length=16384,
            description="The flagship model across audio, vision, and text by OpenAI",
            link="https://openai.com/index/hello-gpt-4o/",
            function_calling=True,
        ),
        ModelMetadata(
            model=["o1", "o1-2024-12-17"],
            context_length=200000,
            max_output_length=100000,
            description="Reasoning model by OpenAI",
            link="https://platform.openai.com/docs/models#o1",
            function_calling=True,
        ),
        ModelMetadata(
            model=["o1-mini", "o1-mini-2024-09-12"],
            context_length=128000,
            max_output_length=65536,
            description="Reasoning model by OpenAI",
            link="https://platform.openai.com/docs/models#o1",
            function_calling=True,
        ),
        ModelMetadata(
            model=["o1-preview", "o1-preview-2024-09-12"],
            context_length=128000,
            max_output_length=32768,
            description="Reasoning model by OpenAI",
            link="https://platform.openai.com/docs/models#o1",
            function_calling=True,
        ),
        ModelMetadata(
            model=["o3-mini", "o3-mini-2025-01-31"],
            context_length=200000,
            max_output_length=100000,
            description="Reasoning model by OpenAI",
            link="https://platform.openai.com/docs/models#o3-mini",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-4-turbo",
                "gpt-4-turbo-2024-04-09",
                "gpt-4-turbo-preview",
                "gpt-4-0125-preview",
                "gpt-4-1106-preview",
            ],
            context_length=128000,
            max_output_length=4096,
            description="GPT-4-Turbo by OpenAI",
            link="https://platform.openai.com/docs/models#gpt-4-turbo-and-gpt-4",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-4",
                "gpt-4-0613",
                "gpt-4-0314",
            ],
            context_length=8192,
            max_output_length=8192,
            description="GPT-4-Turbo by OpenAI",
            link="https://platform.openai.com/docs/models#gpt-4-turbo-and-gpt-4",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gpt-3.5-turbo-0125",
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-1106",
            ],
            context_length=16385,
            max_output_length=4096,
            description="GPT-3.5 by OpenAI",
            link="https://platform.openai.com/docs/models#gpt-3-5-turbo",
            function_calling=True,
        ),
    ],
)
