import logging
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Iterator, Optional, Type, Union

from dbgpt.core import MessageConverter, ModelMetadata, ModelOutput, ModelRequest
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.util.i18n_utils import _

from .chatgpt import OpenAICompatibleDeployModelParameters

logger = logging.getLogger(__name__)


_DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass
class TongyiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Tongyi."""

    provider: str = "proxy/tongyi"

    # api_base: Optional[str] = field(
    #     default="https://dashscope.aliyuncs.com/compatible-mode/v1",
    #     metadata={
    #         "help": _("The base url of the tongyi API."),
    #     },
    # )
    #
    api_key: Optional[str] = field(
        default="${env:DASHSCOPE_API_KEY}",
        metadata={
            "help": _("The API key of the tongyi API."),
        },
    )


def tongyi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: TongyiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    for r in client.sync_generate_stream(request):
        yield r


class TongyiLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_region: Optional[str] = None,
        model_alias: Optional[str] = "tongyi_proxyllm",
        context_length: Optional[int] = 4096,
        executor: Optional[Executor] = None,
    ):
        try:
            import dashscope
            from dashscope import Generation
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: dashscope "
                "Please install dashscope by command `pip install dashscope"
            ) from exc
        if not model:
            model = Generation.Models.qwen_turbo
        if api_key:
            dashscope.api_key = api_key
        if api_region:
            dashscope.api_region = api_region
        self._model = model

        super().__init__(
            model_names=[model, model_alias],
            context_length=context_length,
            executor=executor,
        )

    @classmethod
    def new_client(
        cls,
        model_params: TongyiDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "TongyiLLMClient":
        return cls(
            model=model_params.real_provider_model_name,
            api_key=model_params.api_key,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
            executor=default_executor,
        )

    @classmethod
    def param_class(cls) -> Type[TongyiDeployModelParameters]:
        return TongyiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return tongyi_generate_stream

    @property
    def default_model(self) -> str:
        return self._model

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
        from dashscope import Generation

        request = self.local_covert_message(request, message_converter)

        messages = request.to_common_messages()

        model = request.model or self._model
        try:
            gen = Generation()
            res = gen.call(
                model,
                messages=messages,
                top_p=request.top_p or 0.8,
                stream=True,
                result_format="message",
                stop=request.stop,
            )
            for r in res:
                if r:
                    if r["status_code"] == 200:
                        content = r["output"]["choices"][0]["message"].get("content")
                        yield ModelOutput(text=content, error_code=0)
                    else:
                        content = r["code"] + ":" + r["message"]
                        yield ModelOutput(text=content, error_code=-1)
        except Exception as e:
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )


register_proxy_model_adapter(
    TongyiLLMClient,
    supported_models=[
        ModelMetadata(
            model=["qwen-max-latest", "qwen-max-2025-01-25", "qwen-max"],
            context_length=32 * 1024,
            description="Qwen Max by Qwen",
            link="https://bailian.console.aliyun.com/#/model-market/detail/qwen-max-latest",  # noqa
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-r1",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://bailian.console.aliyun.com/#/model-market/detail/deepseek-r1",
            function_calling=True,
        ),
        ModelMetadata(
            model="deepseek-v3",
            context_length=64 * 1024,
            max_output_length=8 * 1024,
            description="DeepSeek-R1 by DeepSeek",
            link="https://bailian.console.aliyun.com/#/model-market/detail/deepseek-v3",
            function_calling=True,
        ),
        # More models see: https://bailian.console.aliyun.com/#/model-market
    ],
)
