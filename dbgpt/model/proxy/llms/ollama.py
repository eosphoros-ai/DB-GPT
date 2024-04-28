import logging
from concurrent.futures import Executor
from typing import Iterator, Optional

from dbgpt.core import MessageConverter, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

logger = logging.getLogger(__name__)


def ollama_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=4096
):
    client: OllamaLLMClient = model.proxy_llm_client
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


class OllamaLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        model_alias: Optional[str] = "ollama_proxyllm",
        context_length: Optional[int] = 4096,
        executor: Optional[Executor] = None,
    ):
        if not model:
            model = "llama2"
        if not host:
            host = "http://localhost:11434"
        self._model = model
        self._host = host

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
    ) -> "OllamaLLMClient":
        return cls(
            model=model_params.proxyllm_backend,
            host=model_params.proxy_server_url,
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
        try:
            import ollama
            from ollama import Client
        except ImportError as e:
            raise ValueError(
                "Could not import python package: ollama "
                "Please install ollama by command `pip install ollama"
            ) from e
        request = self.local_covert_message(request, message_converter)
        messages = request.to_common_messages()

        model = request.model or self._model
        client = Client(self._host)
        try:
            stream = client.chat(
                model=model,
                messages=messages,
                stream=True,
            )
            content = ""
            for chunk in stream:
                content = content + chunk["message"]["content"]
                yield ModelOutput(text=content, error_code=0)
        except ollama.ResponseError as e:
            return ModelOutput(
                text=f"**Ollama Response Error, Please CheckErrorInfo.**: {e}",
                error_code=-1,
            )
