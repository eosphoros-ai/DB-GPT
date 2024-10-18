import logging
from concurrent.futures import Executor
from typing import Iterator, Optional

from dbgpt.core import MessageConverter, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

logger = logging.getLogger(__name__)


def tongyi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    client: TongyiLLMClient = model.proxy_llm_client
    context = ModelRequestContext(stream=True, user_name=params.get("user_name"))
    request = ModelRequest.build_request(
        client.default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
        stop=params.get("stop"),
    )
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
        model_params: ProxyModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "TongyiLLMClient":
        return cls(
            model=model_params.proxyllm_backend,
            api_key=model_params.proxy_api_key,
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
        from dashscope import Generation

        request = self.local_covert_message(request, message_converter)

        messages = request.to_common_messages()

        model = request.model or self._model
        try:
            gen = Generation()
            res = gen.call(
                model,
                messages=messages,
                top_p=0.8,
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
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
