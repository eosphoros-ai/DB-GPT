import json
import os
from concurrent.futures import Executor
from typing import AsyncIterator, Optional

from dbgpt.core import MessageConverter, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel


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
        stop=params.get("stop"),
    )
    for r in client.generate_stream(request):
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


def extract_content(line: str):
    if not line.strip():
        return line
    if line.startswith("data: "):
        json_str = line[len("data: ") :]
    else:
        raise ValueError("Error line content ")

    try:
        data = json.loads(json_str)
        if data == "[DONE]":
            return ""

        choices = data.get("choices", [])
        if choices and isinstance(choices, list):
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            return content
        else:
            raise ValueError("Error line content ")
    except json.JSONDecodeError:
        return ""


class SparkLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        model_alias: Optional[str] = "spark_proxyllm",
        context_length: Optional[int] = 4096,
        executor: Optional[Executor] = None,
    ):
        """
        星火大模型API当前有Lite、Pro、Pro-128K、Max、Max-32K和4.0 Ultra六个版本
        Spark4.0 Ultra 请求地址，对应的domain参数为4.0Ultra
        Spark Max-32K请求地址，对应的domain参数为max-32k
        Spark Max请求地址，对应的domain参数为generalv3.5
        Spark Pro-128K请求地址，对应的domain参数为pro-128k：
        Spark Pro请求地址，对应的domain参数为generalv3：
        Spark Lite请求地址，对应的domain参数为lite：
        https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_3-%E8%AF%B7%E6%B1%82%E8%AF%B4%E6%98%8E
        """
        self._model = model or os.getenv("XUNFEI_SPARK_API_MODEL")
        self._api_base = os.getenv("PROXY_SERVER_URL")
        self._api_password = os.getenv("XUNFEI_SPARK_API_PASSWORD")
        if not self._model:
            raise ValueError("model can't be empty")
        if not self._api_base:
            raise ValueError("api_base can't be empty")
        if not self._api_password:
            raise ValueError("api_password can't be empty")

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
            model_alias=model_params.model_name,
            context_length=model_params.max_context_size,
            executor=default_executor,
        )

    @property
    def default_model(self) -> str:
        return self._model

    def generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> AsyncIterator[ModelOutput]:
        """
        reference:
        https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_3-%E8%AF%B7%E6%B1%82%E8%AF%B4%E6%98%8E
        """
        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages(support_system_role=False)
        try:
            import requests
        except ImportError as e:
            raise ValueError(
                "Could not import python package: requests "
                "Please install requests by command `pip install requests"
            ) from e

        data = {
            "model": self._model,  # 指定请求的模型
            "messages": messages,
            "temperature": request.temperature,
            "stream": True,
        }
        header = {
            "Authorization": f"Bearer {self._api_password}"  # 注意此处替换自己的APIPassword
        }
        response = requests.post(self._api_base, headers=header, json=data, stream=True)
        # 流式响应解析示例
        response.encoding = "utf-8"
        try:
            content = ""
            # data: {"code":0,"message":"Success","sid":"cha000bf865@dx19307263c06b894532","id":"cha000bf865@dx19307263c06b894532","created":1730991766,"choices":[{"delta":{"role":"assistant","content":"你好"},"index":0}]}
            # data: [DONE]
            for line in response.iter_lines(decode_unicode=True):
                print("llm out:", line)
                content = content + extract_content(line)
                yield ModelOutput(text=content, error_code=0)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
