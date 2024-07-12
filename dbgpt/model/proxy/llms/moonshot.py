import logging
import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Optional, Union, cast

from openai._streaming import Stream

from dbgpt.core import MessageConverter, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

from .chatgpt import OpenAILLMClient

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

_MOONSHOT_DEFAULT_MODEL = "moonshot-v1-8k"

logger = logging.getLogger(__name__)


async def moonshot_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: MoonshotLLMClient = cast(MoonshotLLMClient, model.proxy_llm_client)
    context = ModelRequestContext(stream=True, user_name=params.get("user_name"))
    request = ModelRequest.build_request(
        client.default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
    )
    async for r in client.generate_stream(request):
        yield r


class MoonshotLLMClient(OpenAILLMClient):
    """Moonshot LLM Client.

    Moonshot's API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _MOONSHOT_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = "moonshot_proxyllm",
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        api_base = (
            api_base or os.getenv("MOONSHOT_API_BASE") or "https://api.moonshot.cn/v1"
        )
        api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        model = model or _MOONSHOT_DEFAULT_MODEL
        if not context_length:
            if "128k" in model:
                context_length = 1024 * 128
            elif "32k" in model:
                context_length = 1024 * 32
            else:
                # 8k
                context_length = 1024 * 8

        if not api_key:
            raise ValueError(
                "Moonshot API key is required, please set 'MOONSHOT_API_KEY' in "
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
                "Moonshot API requires openai>=1.0, please upgrade it by "
                "`pip install --upgrade 'openai>=1.0'`"
            )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _MOONSHOT_DEFAULT_MODEL
        return model

    async def generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> AsyncIterator[ModelOutput]:
        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages()
        payload = self._build_request(request, stream=True)
        logger.info(
            f"Send request to moonshot({self._openai_version}), payload: {payload}\n\n messages:\n{messages}"
        )
        chat_completion: Stream = self.client.chat.completions.create(
            messages=messages, **payload
        )
        text = ""
        for r in chat_completion:
            if len(r.choices) == 0:
                continue
            if r.choices[0].delta.content is not None:
                content = r.choices[0].delta.content
                text += content
                yield ModelOutput(text=text, error_code=0)
