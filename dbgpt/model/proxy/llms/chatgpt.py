from __future__ import annotations

import importlib.metadata as metadata
import logging
from concurrent.futures import Executor
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Union

from dbgpt.core import (
    MessageConverter,
    ModelMetadata,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.model.utils.chatgpt_utils import OpenAIParameters
from dbgpt.util.i18n_utils import _

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

logger = logging.getLogger(__name__)


async def chatgpt_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: OpenAILLMClient = model.proxy_llm_client
    context = ModelRequestContext(stream=True, user_name=params.get("user_name"))
    request = ModelRequest.build_request(
        client.default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
        stop=params.get("stop"),
    )
    async for r in client.generate_stream(request):
        yield r


@register_resource(
    label=_("OpenAI LLM Client"),
    name="openai_llm_client",
    category=ResourceCategory.LLM_CLIENT,
    parameters=[
        Parameter.build_from(
            label=_("OpenAI API Key"),
            name="apk_key",
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
        model_alias: Optional[str] = "chatgpt_proxyllm",
        context_length: Optional[int] = 8192,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        try:
            import openai
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: openai "
                "Please install openai by command `pip install openai"
            ) from exc
        self._openai_version = metadata.version("openai")
        self._openai_less_then_v1 = not self._openai_version >= "1.0.0"
        self.check_sdk_version(self._openai_version)

        self._init_params = OpenAIParameters(
            api_type=api_type,
            api_base=api_base,
            api_key=api_key,
            api_version=api_version,
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

        if self._openai_less_then_v1:
            from dbgpt.model.utils.chatgpt_utils import _initialize_openai

            _initialize_openai(self._init_params)

    @classmethod
    def new_client(
        cls,
        model_params: ProxyModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "OpenAILLMClient":
        return cls(
            api_key=model_params.proxy_api_key,
            api_base=model_params.proxy_api_base,
            api_type=model_params.proxy_api_type,
            api_version=model_params.proxy_api_version,
            model=model_params.proxyllm_backend,
            proxies=model_params.http_proxy,
            model_alias=model_params.model_name,
            context_length=max(model_params.max_context_size, 8192),
            full_url=model_params.proxy_server_url,
        )

    def check_sdk_version(self, version: str) -> None:
        """Check the sdk version of the client.

        Raises:
            ValueError: If check failed.
        """
        pass

    @property
    def client(self) -> ClientType:
        if self._openai_less_then_v1:
            raise ValueError(
                "Current model (Load by OpenAILLMClient) require openai.__version__>=1.0.0"
            )
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
            model = "gpt-35-turbo" if self._api_type == "azure" else "gpt-3.5-turbo"
        return model

    def _build_request(
        self, request: ModelRequest, stream: Optional[bool] = False
    ) -> Dict[str, Any]:
        payload = {"stream": stream}
        model = request.model or self.default_model
        if self._openai_less_then_v1 and self._api_type == "azure":
            payload["engine"] = model
        else:
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
            f"Send request to openai({self._openai_version}), payload: {payload}\n\n messages:\n{messages}"
        )
        try:
            if self._openai_less_then_v1:
                return await self.generate_less_then_v1(messages, payload)
            else:
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
            f"Send request to openai({self._openai_version}), payload: {payload}\n\n messages:\n{messages}"
        )
        if self._openai_less_then_v1:
            async for r in self.generate_stream_less_then_v1(messages, payload):
                yield r
        else:
            async for r in self.generate_stream_v1(messages, payload):
                yield r

    async def generate_v1(
        self, messages: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> ModelOutput:
        chat_completion = await self.client.chat.completions.create(
            messages=messages, **payload
        )
        text = chat_completion.choices[0].message.content
        usage = chat_completion.usage.dict()
        return ModelOutput(text=text, error_code=0, usage=usage)

    async def generate_less_then_v1(
        self, messages: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> ModelOutput:
        import openai

        chat_completion = await openai.ChatCompletion.acreate(
            messages=messages, **payload
        )
        text = chat_completion.choices[0].message.content
        usage = chat_completion.usage.to_dict()
        return ModelOutput(text=text, error_code=0, usage=usage)

    async def generate_stream_v1(
        self, messages: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> AsyncIterator[ModelOutput]:
        chat_completion = await self.client.chat.completions.create(
            messages=messages, **payload
        )
        text = ""
        async for r in chat_completion:
            if len(r.choices) == 0:
                continue
            # Check for empty 'choices' issue in Azure GPT-4o responses
            if r.choices[0] is not None and r.choices[0].delta is None:
                continue
            if r.choices[0].delta.content is not None:
                content = r.choices[0].delta.content
                text += content
                yield ModelOutput(text=text, error_code=0)

    async def generate_stream_less_then_v1(
        self, messages: List[Dict[str, Any]], payload: Dict[str, Any]
    ) -> AsyncIterator[ModelOutput]:
        import openai

        res = await openai.ChatCompletion.acreate(messages=messages, **payload)
        text = ""
        async for r in res:
            if not r.get("choices"):
                continue
            if r["choices"][0]["delta"].get("content") is not None:
                content = r["choices"][0]["delta"]["content"]
                text += content
                yield ModelOutput(text=text, error_code=0)

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
        # TODO: This is a temporary solution. We should have a better way to get the context length.
            eg. get real context length from the openai api.
        """
        return self._context_length
