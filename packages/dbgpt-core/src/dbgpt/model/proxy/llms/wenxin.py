import json
import logging
import os
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Iterator, Optional, Type, Union

from cachetools import TTLCache, cached

from dbgpt.core import (
    MessageConverter,
    ModelMetadata,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.util.i18n_utils import _

# https://cloud.baidu.com/doc/WENXINWORKSHOP/s/clntwmv7t
MODEL_VERSION_MAPPING = {
    "ERNIE-Bot-4.0": "completions_pro",
    "ERNIE-Bot-8K": "ernie_bot_8k",
    "ERNIE-Bot": "completions",
    "ERNIE-Bot-turbo": "eb-instant",
}

_DEFAULT_MODEL = "ERNIE-Bot"

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("Baidu Wenxin Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Baidu Wenxin proxy LLM configuration."),
    documentation_url="https://cloud.baidu.com/doc/WENXINWORKSHOP/s/clntwmv7t",
    show_in_ui=False,
)
@dataclass
class WenxinDeployModelParameters(LLMDeployModelParameters):
    """Deploy model parameters for Wenxin."""

    provider: str = "proxy/wenxin"

    api_key: Optional[str] = field(
        default="${env:WEN_XIN_API_KEY}",
        metadata={
            "help": _("The API key of the Wenxin API."),
            "tags": "privacy",
        },
    )
    api_secret: Optional[str] = field(
        default="${env:WEN_XIN_API_SECRET}",
        metadata={
            "help": _("The API secret key of the Wenxin API."),
            "tags": "privacy",
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

    concurrency: Optional[int] = field(
        default=100, metadata={"help": _("Model concurrency limit")}
    )


@cached(TTLCache(1, 1800))
def _build_access_token(api_key: str, secret_key: str) -> str:
    """
    Generate Access token according AK, SK
    """
    import requests

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }

    res = requests.get(url=url, params=params)

    if res.status_code == 200:
        return res.json().get("access_token")


def _to_wenxin_messages(request: ModelRequest):
    """Convert messages to wenxin compatible format

    See https://cloud.baidu.com/doc/WENXINWORKSHOP/s/jlil56u11
    """
    messages, system_messages = request.split_messages()
    if len(system_messages) > 1:
        raise ValueError("Wenxin only support one system message")
    str_system_message = system_messages[0] if len(system_messages) > 0 else ""
    return messages, str_system_message


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
        model_alias: Optional[str] = _DEFAULT_MODEL,
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
        self._api_key = self._resolve_env_vars(api_key)
        self._api_secret = self._resolve_env_vars(api_secret)
        self._model_version = model_version

        super().__init__(
            model_names=[model, model_alias],
            context_length=context_length,
            executor=executor,
        )

    @classmethod
    def new_client(
        cls,
        model_params: WenxinDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "WenxinLLMClient":
        return cls(
            model=model_params.real_provider_model_name,
            api_key=model_params.api_key,
            api_secret=model_params.api_secret,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
            executor=default_executor,
        )

    @classmethod
    def param_class(cls) -> Type[WenxinDeployModelParameters]:
        return WenxinDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return wenxin_generate_stream

    @property
    def default_model(self) -> str:
        return self._model

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
        try:
            import requests
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: requests "
                "Please install requests by running `pip install requests`."
            ) from exc

        request = self.local_covert_message(request, message_converter)

        try:
            access_token = _build_access_token(self._api_key, self._api_secret)

            headers = {"Content-Type": "application/json", "Accept": "application/json"}

            proxy_server_url = (
                f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/"
                f"wenxinworkshop/chat/{self._model_version}?access_token={access_token}"
            )

            if not access_token:
                raise RuntimeError(
                    "Failed to get access token. please set the correct api_key and "
                    "secret key."
                )

            history, system_message = _to_wenxin_messages(request)
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
                f"Send request to {proxy_server_url} with real model {self._model}, "
                f"model version {self._model_version}"
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
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )


register_proxy_model_adapter(
    WenxinLLMClient,
    supported_models=[
        ModelMetadata(
            model=["ERNIE-Bot-4.0", "ERNIE-Bot-8K", "ERNIE-Bot", "ERNIE-Bot-turbo"],
            description="ERNIE-Bot-4.0 by Baidu",
            link="https://cloud.baidu.com/doc/WENXINWORKSHOP/s/clntwmv7t",
            function_calling=True,
        ),
    ],
)
