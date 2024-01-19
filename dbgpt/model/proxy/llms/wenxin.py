import json
import logging
import os
from concurrent.futures import Executor
from typing import Iterator, List, Optional

import requests
from cachetools import TTLCache, cached

from dbgpt.core import (
    MessageConverter,
    ModelMessage,
    ModelMessageRoleType,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

# https://cloud.baidu.com/doc/WENXINWORKSHOP/s/clntwmv7t
MODEL_VERSION_MAPPING = {
    "ERNIE-Bot-4.0": "completions_pro",
    "ERNIE-Bot-8K": "ernie_bot_8k",
    "ERNIE-Bot": "completions",
    "ERNIE-Bot-turbo": "eb-instant",
}

_DEFAULT_MODEL = "ERNIE-Bot"

logger = logging.getLogger(__name__)


@cached(TTLCache(1, 1800))
def _build_access_token(api_key: str, secret_key: str) -> str:
    """
    Generate Access token according AK, SK
    """

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }

    res = requests.get(url=url, params=params)

    if res.status_code == 200:
        return res.json().get("access_token")


def _to_wenxin_messages(messages: List[ModelMessage]):
    """Convert messages to wenxin compatible format

    See https://cloud.baidu.com/doc/WENXINWORKSHOP/s/jlil56u11
    """
    wenxin_messages = []
    system_messages = []
    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            wenxin_messages.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            system_messages.append(message.content)
        elif message.role == ModelMessageRoleType.AI:
            wenxin_messages.append({"role": "assistant", "content": message.content})
        else:
            pass
    if len(system_messages) > 1:
        raise ValueError("Wenxin only support one system message")
    str_system_message = system_messages[0] if len(system_messages) > 0 else ""
    return wenxin_messages, str_system_message


def wenxin_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: WenxinLLMClient = model.proxy_llm_client
    context = ModelRequestContext(stream=True, user_name=params.get("user_name"))
    request = ModelRequest.build_request(
        client.default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
    )
    for r in client.sync_generate_stream(request):
        yield r


class WenxinLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        model_version: Optional[str] = None,
        model_alias: Optional[str] = "wenxin_proxyllm",
        context_length: Optional[int] = 8192,
        executor: Optional[Executor] = None,
    ):
        if not model:
            model = _DEFAULT_MODEL
        if not api_key:
            api_key = os.getenv("WEN_XIN_API_KEY")
        if not api_secret:
            api_secret = os.getenv("WEN_XIN_API_SECRET")
        if not model_version:
            if model:
                model_version = MODEL_VERSION_MAPPING.get(model)
            else:
                model_version = os.getenv("WEN_XIN_MODEL_VERSION")
        if not api_key:
            raise ValueError("api_key can't be empty")
        if not api_secret:
            raise ValueError("api_secret can't be empty")
        if not model_version:
            raise ValueError("model_version can't be empty")
        self._model = model
        self._api_key = api_key
        self._api_secret = api_secret
        self._model_version = model_version

        super().__init__(
            model_names=[model, model_alias],
            context_length=context_length,
            executor=executor,
        )

    @classmethod
    def new_client(
        cls,
        model_params: ProxyModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "WenxinLLMClient":
        return cls(
            model=model_params.proxyllm_backend,
            api_key=model_params.proxy_api_key,
            api_secret=model_params.proxy_api_secret,
            model_version=model_params.proxy_api_version,
            model_alias=model_params.model_name,
            context_length=model_params.max_context_size,
            executor=default_executor,
        )

    @property
    def default_model(self) -> str:
        return self._model

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
        request = self.local_covert_message(request, message_converter)

        try:
            access_token = _build_access_token(self._api_key, self._api_secret)

            headers = {"Content-Type": "application/json", "Accept": "application/json"}

            proxy_server_url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self._model_version}?access_token={access_token}"

            if not access_token:
                raise RuntimeError(
                    "Failed to get access token. please set the correct api_key and secret key."
                )

            history, system_message = _to_wenxin_messages(request.get_messages())
            payload = {
                "messages": history,
                "system": system_message,
                "temperature": request.temperature,
                "stream": True,
            }

            text = ""
            res = requests.post(
                proxy_server_url, headers=headers, json=payload, stream=True
            )
            logger.info(
                f"Send request to {proxy_server_url} with real model {self._model}, model version {self._model_version}"
            )
            for line in res.iter_lines():
                if line:
                    if not line.startswith(b"data: "):
                        error_message = line.decode("utf-8")
                        yield ModelOutput(text=error_message, error_code=1)
                    else:
                        json_data = line.split(b": ", 1)[1]
                        decoded_line = json_data.decode("utf-8")
                        if decoded_line.lower() != "[DONE]".lower():
                            obj = json.loads(json_data)
                            if obj["result"] is not None:
                                content = obj["result"]
                                text += content
                        yield ModelOutput(text=text, error_code=0)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
