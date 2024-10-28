import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from dbgpt.core import ModelRequest, ModelRequestContext
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

from .chatgpt import OpenAILLMClient

if TYPE_CHECKING:
    from httpx._types import ProxiesTypes
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    ClientType = Union[AsyncAzureOpenAI, AsyncOpenAI]

_YI_DEFAULT_MODEL = "yi-34b-chat-0205"


async def yi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: YiLLMClient = model.proxy_llm_client
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


class YiLLMClient(OpenAILLMClient):
    """Yi LLM Client.

    Yi' API is compatible with OpenAI's API, so we inherit from OpenAILLMClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = _YI_DEFAULT_MODEL,
        proxies: Optional["ProxiesTypes"] = None,
        timeout: Optional[int] = 240,
        model_alias: Optional[str] = "yi_proxyllm",
        context_length: Optional[int] = None,
        openai_client: Optional["ClientType"] = None,
        openai_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        api_base = (
            api_base or os.getenv("YI_API_BASE") or "https://api.lingyiwanwu.com/v1"
        )
        api_key = api_key or os.getenv("YI_API_KEY")
        model = model or _YI_DEFAULT_MODEL
        if not context_length:
            if "200k" in model:
                context_length = 200 * 1024
            else:
                context_length = 4096

        if not api_key:
            raise ValueError(
                "Yi API key is required, please set 'YI_API_KEY' in environment "
                "variable or pass it to the client."
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
            **kwargs
        )

    @property
    def default_model(self) -> str:
        model = self._model
        if not model:
            model = _YI_DEFAULT_MODEL
        return model
