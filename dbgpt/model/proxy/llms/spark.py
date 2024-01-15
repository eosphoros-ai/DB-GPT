import base64
import hashlib
import hmac
import json
import os
from concurrent.futures import Executor
from datetime import datetime
from time import mktime
from typing import Iterator, Optional
from urllib.parse import urlencode, urlparse

from dbgpt.core import MessageConverter, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

SPARK_DEFAULT_API_VERSION = "v3"


def getlength(text):
    length = 0
    for content in text:
        temp = content["content"]
        leng = len(temp)
        length += leng
    return length


def checklen(text):
    while getlength(text) > 8192:
        del text[0]
    return text


def spark_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: SparkLLMClient = model.proxy_llm_client
    context = ModelRequestContext(
        stream=True,
        user_name=params.get("user_name"),
        request_id=params.get("request_id"),
    )
    request = ModelRequest.build_request(
        client.default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
    )
    for r in client.sync_generate_stream(request):
        yield r


def get_response(request_url, data):
    from websockets.sync.client import connect

    with connect(request_url) as ws:
        ws.send(json.dumps(data, ensure_ascii=False))
        result = ""
        while True:
            try:
                chunk = ws.recv()
                response = json.loads(chunk)
                print("look out the response: ", response)
                choices = response.get("payload", {}).get("choices", {})
                if text := choices.get("text"):
                    result += text[0]["content"]
                if choices.get("status") == 2:
                    break
            except Exception as e:
                raise e
    yield result


class SparkAPI:
    def __init__(
        self, appid: str, api_key: str, api_secret: str, spark_url: str
    ) -> None:
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = urlparse(spark_url).netloc
        self.path = urlparse(spark_url).path

        self.spark_url = spark_url

    def gen_url(self):
        from wsgiref.handlers import format_date_time

        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + self.host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + self.path + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding="utf-8")

        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
            encoding="utf-8"
        )

        # 将请求的鉴权参数组合为字典
        v = {"authorization": authorization, "date": date, "host": self.host}
        # 拼接鉴权参数，生成url
        url = self.spark_url + "?" + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url


class SparkLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        app_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_base: Optional[str] = None,
        api_domain: Optional[str] = None,
        model_version: Optional[str] = None,
        model_alias: Optional[str] = "spark_proxyllm",
        context_length: Optional[int] = 4096,
        executor: Optional[Executor] = None,
    ):
        if not model_version:
            model_version = model or os.getenv("XUNFEI_SPARK_API_VERSION")
        if not api_base:
            if model_version == SPARK_DEFAULT_API_VERSION:
                api_base = "ws://spark-api.xf-yun.com/v3.1/chat"
                domain = "generalv3"
            else:
                api_base = "ws://spark-api.xf-yun.com/v2.1/chat"
                domain = "generalv2"
            if not api_domain:
                api_domain = domain
        self._model = model
        self._model_version = model_version
        self._api_base = api_base
        self._domain = api_domain
        self._app_id = app_id or os.getenv("XUNFEI_SPARK_APPID")
        self._api_secret = api_secret or os.getenv("XUNFEI_SPARK_API_SECRET")
        self._api_key = api_key or os.getenv("XUNFEI_SPARK_API_KEY")

        if not self._app_id:
            raise ValueError("app_id can't be empty")
        if not self._api_key:
            raise ValueError("api_key can't be empty")
        if not self._api_secret:
            raise ValueError("api_secret can't be empty")

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
    ) -> "SparkLLMClient":
        return cls(
            model=model_params.proxyllm_backend,
            app_id=model_params.proxy_api_app_id,
            api_key=model_params.proxy_api_key,
            api_secret=model_params.proxy_api_secret,
            api_base=model_params.proxy_api_base,
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
        messages = request.to_common_messages(support_system_role=False)
        request_id = request.context.request_id or "1"
        data = {
            "header": {"app_id": self._app_id, "uid": request_id},
            "parameter": {
                "chat": {
                    "domain": self._domain,
                    "random_threshold": 0.5,
                    "max_tokens": request.max_new_tokens,
                    "auditing": "default",
                    "temperature": request.temperature,
                }
            },
            "payload": {"message": {"text": messages}},
        }

        spark_api = SparkAPI(
            self._app_id, self._api_key, self._api_secret, self._api_base
        )
        request_url = spark_api.gen_url()
        try:
            for text in get_response(request_url, data):
                yield ModelOutput(text=text, error_code=0)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
