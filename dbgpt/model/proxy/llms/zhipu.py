from concurrent.futures import Executor
from typing import Iterator, Optional

from dbgpt.core import MessageConverter, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

CHATGLM_DEFAULT_MODEL = "chatglm_pro"


def zhipu_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://open.bigmodel.cn/dev/api#overview"""
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    # TODO: Support convert_to_compatible_format config, zhipu not support system message
    # convert_to_compatible_format = params.get("convert_to_compatible_format", False)
    # history, systems = __convert_2_zhipu_messages(messages)
    client: ZhipuLLMClient = model.proxy_llm_client
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


class ZhipuLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        model_alias: Optional[str] = "zhipu_proxyllm",
        context_length: Optional[int] = 8192,
        executor: Optional[Executor] = None,
    ):
        try:
            import zhipuai

        except ImportError as exc:
            raise ValueError(
                "Could not import python package: zhipuai "
                "Please install dashscope by command `pip install zhipuai"
            ) from exc
        if not model:
            model = CHATGLM_DEFAULT_MODEL
        if api_key:
            zhipuai.api_key = api_key
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
    ) -> "ZhipuLLMClient":
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
        import zhipuai

        request = self.local_covert_message(request, message_converter)

        messages = request.to_common_messages(support_system_role=False)

        model = request.model or self._model
        try:
            res = zhipuai.model_api.sse_invoke(
                model=model,
                prompt=messages,
                temperature=request.temperature,
                # top_p=params.get("top_p"),
                incremental=False,
            )
            for r in res.events():
                if r.event == "add":
                    yield ModelOutput(text=r.data, error_code=0)
                elif r.event == "error":
                    yield ModelOutput(text=r.data, error_code=1)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
