import json
import os
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Iterator, Optional, Type, Union

from dbgpt.core import MessageConverter, ModelMetadata, ModelOutput, ModelRequest
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.util.i18n_utils import _

from .chatgpt import OpenAICompatibleDeployModelParameters


@auto_register_resource(
    label=_("Xunfei Spark Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Xunfei Spark proxy LLM configuration."),
    documentation_url="https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E",
    show_in_ui=False,
)
@dataclass
class SparkDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Spark."""

    provider: str = "proxy/spark"

    api_base: Optional[str] = field(
        default="${env:XUNFEI_SPARK_API_BASE:-https://spark-api-open.xf-yun.com/v1}",
        metadata={
            "help": _("The base url of the Spark API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:XUNFEI_SPARK_API_KEY}",
        metadata={
            "help": _("The API key of the Spark API."),
            "tags": "privacy",
        },
    )


def spark_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: SparkLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    for r in client.sync_generate_stream(request):
        yield r


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
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
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
        self._api_base = self._resolve_env_vars(api_base)
        self._api_key = self._resolve_env_vars(
            api_key
            or os.getenv("XUNFEI_SPARK_API_KEY")
            or os.getenv("XUNFEI_SPARK_API_PASSWORD")
        )
        if not self._model:
            raise ValueError("model can't be empty")
        if not self._api_base:
            raise ValueError("api_base can't be empty")
        if not self._api_key:
            raise ValueError("Spark API key is required, please provide it.")

        super().__init__(
            model_names=[model, model_alias],
            context_length=context_length,
            executor=executor,
        )

    @classmethod
    def new_client(
        cls,
        model_params: SparkDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "SparkLLMClient":
        return cls(
            model=model_params.real_provider_model_name,
            api_base=model_params.api_base,
            api_key=model_params.api_key,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
            executor=default_executor,
        )

    @classmethod
    def param_class(cls) -> Type[SparkDeployModelParameters]:
        return SparkDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return spark_generate_stream

    @property
    def default_model(self) -> str:
        return self._model

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
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
            # Please replace the APIPassword with your own
            "Authorization": f"Bearer {self._api_key}"
        }
        url = self._api_base
        if url.endswith("/"):
            url = url[:-1]
        url = f"{url}/chat/completions"
        response = requests.post(url, headers=header, json=data, stream=True)
        response.encoding = "utf-8"
        try:
            content = ""
            # data: {"code":0,"message":"Success","sid":"cha000bf865@dx19307263c06b894532","id":"cha000bf865@dx19307263c06b894532","created":1730991766,"choices":[{"delta":{"role":"assistant","content":"你好"},"index":0}]} #noqa
            # data: [DONE]
            for line in response.iter_lines(decode_unicode=True):
                print("llm out:", line)
                content = content + extract_content(line)
                yield ModelOutput(text=content, error_code=0)
        except Exception as e:
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )


register_proxy_model_adapter(
    SparkLLMClient,
    supported_models=[
        ModelMetadata(
            model="lite",
            # Maybe not correct, the value inferred from max_output_length
            context_length=14096,
            max_output_length=14096,
            description="Xunfei Spark Lite model",
            link="https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model="pro-128k",
            context_length=128 * 1024,
            max_output_length=14096,
            description="Xunfei Spark Pro-128K model",
            link="https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model=["generalv3", "generalv3.5", "4.0Ultra"],
            # Maybe not correct, the value inferred from max_output_length
            context_length=18192,
            max_output_length=18192,
            description="Xunfei Spark General model",
            link="https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model=["pro-128k"],
            context_length=128 * 1024,
            max_output_length=18192,
            description="Xunfei Spark Pro-128K model",
            link="https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model="max-32k",
            context_length=32 * 1024,
            max_output_length=18192,
            description="Xunfei Spark Max-32K model",
            link="https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E",  # noqa
            function_calling=True,
        ),
    ],
)
