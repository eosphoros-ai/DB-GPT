"""llama.cpp server adapter."""

import dataclasses
import logging
from typing import Dict, Optional, Type

from dbgpt.core import ModelOutput
from dbgpt.model.adapter.base import ConversationAdapter, LLMModelAdapter
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import ModelParameters

logger = logging.getLogger(__name__)
try:
    from llama_cpp_server_py_core import (
        ChatCompletionRequest,
        ChatCompletionStreamResponse,
        LlamaCppServer,
        ServerConfig,
        ServerProcess,
    )
except ImportError:
    logger.error(
        "Failed to import llama_cpp_server_py_core, please install it first by `pip install llama-cpp-server-py-core`"
    )
    raise


@dataclasses.dataclass
class LlamaServerParameters(ServerConfig, ModelParameters):
    lora_files: Optional[str] = dataclasses.field(
        default=None, metadata={"help": "Lora files path"}
    )

    def __post_init__(self):
        if self.model_name:
            self.model_alias = self.model_name

        if self.model_path and not self.model_file:
            self.model_file = self.model_path

        if self.lora_files and isinstance(self.lora_files, str):
            self.lora_files = self.lora_files.split(",")  # type: ignore
        elif not self.lora_files:
            self.lora_files = []  # type: ignore

        if self.model_path:
            self.model_hf_repo = None
            self.model_hf_file = None


class LLamaServerModelAdapter(LLMModelAdapter):
    def new_adapter(self, **kwargs) -> "LLamaServerModelAdapter":
        return self.__class__()

    def model_type(self) -> str:
        return ModelType.LLAMA_CPP_SERVER

    def model_param_class(self, model_type: str = None) -> Type[LlamaServerParameters]:
        return LlamaServerParameters

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        return None

    def load_from_params(self, params: LlamaServerParameters):
        server = ServerProcess(params)
        server.start(300)
        model_server = LlamaCppServer(server, params)
        return model_server, model_server

    def get_generate_stream_function(self, model, model_path: str):
        return generate_stream


def generate_stream(
    model: LlamaCppServer,
    tokenizer: LlamaCppServer,
    params: Dict,
    device: str,
    context_len: int,
):
    from dbgpt.model.proxy.llms.proxy_model import parse_model_request

    model_request = parse_model_request(params, "", stream=True)

    req = ChatCompletionRequest(
        messages=model_request.to_common_messages(),
        temperature=params.get("temperature", 0.8),
        top_p=params.get("top_p"),
        top_k=params.get("top_k"),
        max_tokens=params.get("max_new_tokens", 2048),
        stop=params.get("stop"),
        stream=True,
        presence_penalty=params.get("presence_penalty"),
        frequency_penalty=params.get("frequency_penalty"),
        user=params.get("user_name"),
    )
    text = ""
    for r in model.stream_chat_completion(req):
        if len(r.choices) == 0:
            continue
        # Check for empty 'choices' issue in Azure GPT-4o responses
        if r.choices[0] is not None and r.choices[0].delta is None:
            continue
        content = r.choices[0].delta.content
        if content is not None:
            content = r.choices[0].delta.content
            text += content
            yield ModelOutput(text=text, error_code=0, usage=r.usage)
        elif text and content is None:
            # Last response is empty, return the text
            yield ModelOutput(text=text, error_code=0, usage=r.usage)
