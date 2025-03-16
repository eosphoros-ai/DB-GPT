from __future__ import annotations

import importlib.metadata as metadata
import logging
import os
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    AsyncIterator,
    Awaitable,
    Callable,
    Optional,
    Tuple,
    Union,
)

from dbgpt.core.awel import TransformStreamAbsOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    OperatorType,
    ViewMetadata,
)
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.core.operators import BaseLLM
from dbgpt.util.chat_util import transform_to_sse
from dbgpt.util.i18n_utils import _

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes, ProxyTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

logger = logging.getLogger(__name__)


@dataclass
class OpenAIParameters:
    """A class to represent a LLM model."""

    api_type: str = "open_ai"
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    api_azure_deployment: Optional[str] = None
    full_url: Optional[str] = None
    proxies: Optional["ProxiesTypes"] = None
    proxy: Optional["ProxyTypes"] = None


def _initialize_openai_v1(init_params: OpenAIParameters):
    try:
        from openai import OpenAI  # noqa: F401
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

    api_azure_deployment = init_params.api_azure_deployment or os.getenv(
        "API_AZURE_DEPLOYMENT"
    )
    if not base_url and full_url:
        base_url = full_url.split("/chat/completions")[0]

    if api_key is None:
        raise ValueError("api_key is required, please set OPENAI_API_KEY environment")
    if base_url and base_url.endswith("/"):
        base_url = base_url[:-1]

    openai_params = {"api_key": api_key}
    if base_url:
        openai_params["base_url"] = base_url
    return openai_params, api_type, api_version, api_azure_deployment


def _build_openai_client(init_params: OpenAIParameters) -> Tuple[str, ClientType]:
    import httpx

    openai_params, api_type, api_version, api_azure_deployment = _initialize_openai_v1(
        init_params
    )
    if api_type == "azure":
        from openai import AsyncAzureOpenAI

        async_client = AsyncAzureOpenAI(
            api_key=openai_params["api_key"],
            api_version=api_version,
            azure_deployment=api_azure_deployment,
            azure_endpoint=openai_params["base_url"],
        )
    else:
        from openai import AsyncOpenAI

        # Remove proxies for httpx AsyncClient when httpx version >= 0.28.0
        httpx_version = metadata.version("httpx")
        if httpx_version >= "0.28.0":
            if init_params.proxy:
                http_client = httpx.AsyncClient(proxy=init_params.proxy)
            else:
                http_client = httpx.AsyncClient()
        elif init_params.proxies:
            http_client = httpx.AsyncClient(proxies=init_params.proxies)
        else:
            http_client = httpx.AsyncClient()
        async_client = AsyncOpenAI(**openai_params, http_client=http_client)
    return api_type, async_client


class OpenAIStreamingOutputOperator(TransformStreamAbsOperator[ModelOutput, str]):
    """Transform ModelOutput to openai stream format."""

    incremental_output = True
    output_format = "SSE"

    metadata = ViewMetadata(
        label=_("OpenAI Streaming Output Operator"),
        name="openai_streaming_output_operator",
        operator_type=OperatorType.TRANSFORM_STREAM,
        category=OperatorCategory.OUTPUT_PARSER,
        description=_("The OpenAI streaming LLM operator."),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Upstream Model Output"),
                "model_output",
                ModelOutput,
                is_list=True,
                description=_("The model output of upstream."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Model Output"),
                "model_output",
                str,
                is_list=True,
                description=_(
                    "The model output after transformed to openai stream format."
                ),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    async def transform_stream(self, model_output: AsyncIterator[ModelOutput]):
        async def model_caller() -> str:
            """Read model name from share data.
            In streaming mode, this transform_stream function will be executed
            before parent operator(Streaming Operator is trigger by downstream
            Operator).
            """
            model_name = await self.current_dag_context.get_from_share_data(
                BaseLLM.SHARE_DATA_KEY_MODEL_NAME
            )
            return model_name

        async for output in _to_openai_stream(model_output, None, model_caller):
            yield output


async def _to_openai_stream(
    output_iter: AsyncIterator[ModelOutput],
    model: Optional[str] = None,
    model_caller: Callable[[], Union[Awaitable[str], str]] = None,
) -> AsyncIterator[str]:
    """Convert the output_iter to openai stream format.

    Args:
        output_iter (AsyncIterator[ModelOutput]): The output iterator.
        model (Optional[str], optional): The model name. Defaults to None.
        model_caller (Callable[[None], Union[Awaitable[str], str]], optional): The
            model caller. Defaults to None.
    """
    import asyncio

    import shortuuid

    from dbgpt.core.schema.api import (
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
    yield transform_to_sse(chunk)
    delta_text = ""
    previous_text = ""
    thinking_text = ""
    previous_thinking_text = ""
    finish_stream_events = []
    async for model_output in output_iter:
        if model is None and model_caller is not None:
            if asyncio.iscoroutinefunction(model_caller):
                model = await model_caller()
            else:
                model = model_caller()
        model_output: ModelOutput = model_output
        if model_output.error_code != 0:
            yield transform_to_sse(model_output.to_dict())
            yield transform_to_sse("[DONE]")
            return
        if model_output.has_text:
            decoded_unicode = model_output.text.replace("\ufffd", "")
            delta_text = decoded_unicode[len(previous_text) :]
            previous_text = (
                decoded_unicode
                if len(decoded_unicode) > len(previous_text)
                else previous_text
            )
        if model_output.has_thinking:
            decoded_unicode = model_output.thinking_text.replace("\ufffd", "")
            thinking_text = decoded_unicode[len(previous_thinking_text) :]
            previous_thinking_text = (
                decoded_unicode
                if len(decoded_unicode) > len(previous_thinking_text)
                else previous_thinking_text
            )

        if not delta_text:
            delta_text = None
        if not thinking_text:
            thinking_text = None
        choice_data = ChatCompletionResponseStreamChoice(
            index=0,
            delta=DeltaMessage(content=delta_text, reasoning_content=thinking_text),
            finish_reason=model_output.finish_reason,
        )
        chunk = ChatCompletionStreamResponse(
            id=id, choices=[choice_data], model=model or ""
        )
        if delta_text is None and thinking_text is None:
            if model_output.finish_reason is not None:
                finish_stream_events.append(chunk)
            continue
        yield transform_to_sse(chunk)
    for finish_chunk in finish_stream_events:
        yield transform_to_sse(finish_chunk)
    yield transform_to_sse("[DONE]")
