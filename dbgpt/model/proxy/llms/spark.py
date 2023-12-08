import json
import base64
import hmac
import hashlib
from websockets.sync.client import connect
from datetime import datetime
from typing import List
from time import mktime
from urllib.parse import urlencode
from urllib.parse import urlparse
from wsgiref.handlers import format_date_time
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
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
    model_params = model.get_params()
    proxy_api_version = model_params.proxyllm_backend or SPARK_DEFAULT_API_VERSION
    proxy_api_key = model_params.proxy_api_key
    proxy_api_secret = model_params.proxy_api_secret
    proxy_app_id = model_params.proxy_api_app_id

    if proxy_api_version == SPARK_DEFAULT_API_VERSION:
        url = "ws://spark-api.xf-yun.com/v3.1/chat"
        domain = "generalv3"
    else:
        url = "ws://spark-api.xf-yun.com/v2.1/chat"
        domain = "generalv2"

    messages: List[ModelMessage] = params["messages"]

    last_user_input = None
    for index in range(len(messages) - 1, -1, -1):
        print(f"index: {index}")
        if messages[index].role == ModelMessageRoleType.HUMAN:
            last_user_input = {"role": "user", "content": messages[index].content}
            del messages[index]
            break

    history = []
    # Add history conversation
    for message in messages:
        # There is no role for system in spark LLM
        if message.role == ModelMessageRoleType.HUMAN or ModelMessageRoleType.SYSTEM:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
        else:
            pass

    question = checklen(history + [last_user_input])

    print('last_user_input.get("content")', last_user_input.get("content"))
    data = {
        "header": {"app_id": proxy_app_id, "uid": str(params.get("request_id", 1))},
        "parameter": {
            "chat": {
                "domain": domain,
                "random_threshold": 0.5,
                "max_tokens": context_len,
                "auditing": "default",
                "temperature": params.get("temperature"),
            }
        },
        "payload": {"message": {"text": question}},
    }

    spark_api = SparkAPI(proxy_app_id, proxy_api_key, proxy_api_secret, url)
    request_url = spark_api.gen_url()
    return get_response(request_url, data)


def get_response(request_url, data):
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
            except Exception:
                break
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
