from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from abc import ABC
import importlib.metadata as metadata
from typing import (
    List,
    Dict,
    Any,
    Optional,
    TYPE_CHECKING,
    Union,
    AsyncIterator,
    Callable,
    Awaitable,
)

from dbgpt.component import ComponentType
from dbgpt.core.operator import BaseLLM
from dbgpt.core.awel import TransformStreamAbsOperator, BaseOperator
from dbgpt.core.interface.llm import ModelMetadata, LLMClient
from dbgpt.core.interface.llm import ModelOutput, ModelRequest
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory

if TYPE_CHECKING:
    import httpx
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI
    from openai import AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

logger = logging.getLogger(__name__)


@dataclass
class OpenAIParameters:
    """A class to represent a LLM model."""

    api_type: str = "open_ai"
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    full_url: Optional[str] = None
    proxies: Optional["ProxiesTypes"] = None


def _initialize_openai_v1(init_params: OpenAIParameters):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ValueError(
            "Could not import python package: openai "
            "Please install openai by command `pip install openai"
        ) from exc

    if not metadata.version("openai") >= "1.0.0":
        raise ImportError("Please upgrade openai package to version 1.0.0 or above")

    api_type: Optional[str] = init_params.api_type
    api_base: Optional[str] = init_params.api_base
    api_key: Optional[str] = init_params.api_key
    api_version: Optional[str] = init_params.api_version
    full_url: Optional[str] = init_params.full_url

    api_type = api_type or os.getenv("OPENAI_API_TYPE", "open_ai")

    base_url = api_base or os.getenv(
        "OPENAI_API_BASE",
        os.getenv("AZURE_OPENAI_ENDPOINT") if api_type == "azure" else None,
    )
    api_key = api_key or os.getenv(
        "OPENAI_API_KEY",
        os.getenv("AZURE_OPENAI_KEY") if api_type == "azure" else None,
    )
    api_version = api_version or os.getenv("OPENAI_API_VERSION")

    if not base_url and full_url:
        base_url = full_url.split("/chat/completions")[0]

    if api_key is None:
        raise ValueError("api_key is required, please set OPENAI_API_KEY environment")
    if base_url is None:
        raise ValueError("base_url is required, please set OPENAI_BASE_URL environment")
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    openai_params = {
        "api_key": api_key,
        "base_url": base_url,
    }
    return openai_params, api_type, api_version


def _build_openai_client(init_params: OpenAIParameters):
    import httpx

    openai_params, api_type, api_version = _initialize_openai_v1(init_params)
    if api_type == "azure":
        from openai import AsyncAzureOpenAI

        return AsyncAzureOpenAI(
            api_key=openai_params["api_key"],
            api_version=api_version,
            azure_endpoint=openai_params["base_url"],
            http_client=httpx.AsyncClient(proxies=init_params.proxies),
        )
    else:
        from openai import AsyncOpenAI

        return AsyncOpenAI(
            **openai_params, http_client=httpx.AsyncClient(proxies=init_params.proxies)
        )


class OpenAILLMClient(LLMClient):
    """An implementation of LLMClient using OpenAI API.

    In order to have as few dependencies as possible, we directly use the http API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = "gpt-3.5-turbo",
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = "chatgpt_proxyllm",
        context_length: Optional[int] = 8192,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._init_params = OpenAIParameters(
            api_type=api_type,
            api_base=api_base,
            api_key=api_key,
            api_version=api_version,
            proxies=proxies,
        )

        self._model = model
        self._proxies = proxies
        self._timeout = timeout
        self._model_alias = model_alias
        self._context_length = context_length
        self._client = openai_client
        self._openai_kwargs = openai_kwargs or {}

    @property
    def client(self) -> ClientType:
        if self._client is None:
            self._client = _build_openai_client(init_params=self._init_params)
        return self._client

    def _build_request(
        self, request: ModelRequest, stream: Optional[bool] = False
    ) -> Dict[str, Any]:
        payload = {"model": request.model or self._model, "stream": stream}

        # Apply openai kwargs
        for k, v in self._openai_kwargs.items():
            payload[k] = v
        if request.temperature:
            payload["temperature"] = request.temperature
        if request.max_new_tokens:
            payload["max_tokens"] = request.max_new_tokens
        return payload

    async def generate(self, request: ModelRequest) -> ModelOutput:
        messages = request.to_openai_messages()
        payload = self._build_request(request)
        try:
            chat_completion = await self.client.chat.completions.create(
                messages=messages, **payload
            )
            text = chat_completion.choices[0].message.content
            usage = chat_completion.usage.dict()
            return ModelOutput(text=text, error_code=0, usage=usage)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )

    async def generate_stream(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelOutput]:
        messages = request.to_openai_messages()
        payload = self._build_request(request, True)
        try:
            chat_completion = await self.client.chat.completions.create(
                messages=messages, **payload
            )
            text = ""
            async for r in chat_completion:
                if len(r.choices) == 0:
                    continue
                if r.choices[0].delta.content is not None:
                    content = r.choices[0].delta.content
                    text += content
                    yield ModelOutput(text=text, error_code=0)
        except Exception as e:
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )

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

    async def count_token(self, model: str, prompt: str) -> int:
        """Count the number of tokens in a given prompt.

        TODO: Get the real number of tokens from the openai api or tiktoken package
        """

        raise NotImplementedError()


class OpenAIStreamingOperator(TransformStreamAbsOperator[ModelOutput, str]):
    """Transform ModelOutput to openai stream format."""

    async def transform_stream(
        self, input_value: AsyncIterator[ModelOutput]
    ) -> AsyncIterator[str]:
        async def model_caller() -> str:
            """Read model name from share data.
            In streaming mode, this transform_stream function will be executed
            before parent operator(Streaming Operator is trigger by downstream Operator).
            """
            return await self.current_dag_context.get_from_share_data(
                BaseLLM.SHARE_DATA_KEY_MODEL_NAME
            )

        async for output in _to_openai_stream(input_value, None, model_caller):
            yield output


class MixinLLMOperator(BaseLLM, BaseOperator, ABC):
    """Mixin class for LLM operator.

    This class extends BaseOperator by adding LLM capabilities.
    """

    def __init__(self, default_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(default_client)
        self._default_llm_client = default_client

    @property
    def llm_client(self) -> LLMClient:
        if not self._llm_client:
            worker_manager_factory: WorkerManagerFactory = (
                self.system_app.get_component(
                    ComponentType.WORKER_MANAGER_FACTORY,
                    WorkerManagerFactory,
                    default_component=None,
                )
            )
            if worker_manager_factory:
                self._llm_client = DefaultLLMClient(worker_manager_factory.create())
            else:
                if self._default_llm_client is None:
                    from dbgpt.model import OpenAILLMClient

                    self._default_llm_client = OpenAILLMClient()
                logger.info(
                    f"Can't find worker manager factory, use default llm client {self._default_llm_client}."
                )
                self._llm_client = self._default_llm_client
        return self._llm_client


async def _to_openai_stream(
    output_iter: AsyncIterator[ModelOutput],
    model: Optional[str] = None,
    model_caller: Callable[[], Union[Awaitable[str], str]] = None,
) -> AsyncIterator[str]:
    """Convert the output_iter to openai stream format.

    Args:
        output_iter (AsyncIterator[ModelOutput]): The output iterator.
        model (Optional[str], optional): The model name. Defaults to None.
        model_caller (Callable[[None], Union[Awaitable[str], str]], optional): The model caller. Defaults to None.
    """
    import json
    import shortuuid
    import asyncio
    from fastchat.protocol.openai_api_protocol import (
        ChatCompletionResponseStreamChoice,
        ChatCompletionStreamResponse,
        DeltaMessage,
    )

    id = f"chatcmpl-{shortuuid.random()}"

    choice_data = ChatCompletionResponseStreamChoice(
        index=0,
        delta=DeltaMessage(role="assistant"),
        finish_reason=None,
    )
    chunk = ChatCompletionStreamResponse(
        id=id, choices=[choice_data], model=model or ""
    )
    yield f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"

    previous_text = ""
    finish_stream_events = []
    async for model_output in output_iter:
        if model_caller is not None:
            if asyncio.iscoroutinefunction(model_caller):
                model = await model_caller()
            else:
                model = model_caller()
        model_output: ModelOutput = model_output
        if model_output.error_code != 0:
            yield f"data: {json.dumps(model_output.to_dict(), ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        decoded_unicode = model_output.text.replace("\ufffd", "")
        delta_text = decoded_unicode[len(previous_text) :]
        previous_text = (
            decoded_unicode
            if len(decoded_unicode) > len(previous_text)
            else previous_text
        )

        if len(delta_text) == 0:
            delta_text = None
        choice_data = ChatCompletionResponseStreamChoice(
            index=0,
            delta=DeltaMessage(content=delta_text),
            finish_reason=model_output.finish_reason,
        )
        chunk = ChatCompletionStreamResponse(id=id, choices=[choice_data], model=model)
        if delta_text is None:
            if model_output.finish_reason is not None:
                finish_stream_events.append(chunk)
            continue
        yield f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"
    for finish_chunk in finish_stream_events:
        yield f"data: {finish_chunk.json(exclude_none=True, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
