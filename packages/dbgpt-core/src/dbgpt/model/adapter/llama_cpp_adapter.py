"""llama.cpp server adapter.

See more details:
https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md

**Features:**
 * LLM inference of F16 and quantized models on GPU and CPU
 * Parallel decoding with multi-user support
 * Continuous batching

The llama.cpp server is pure C++ server, we need to use the llama-cpp-server-py-core
to interact with it.
"""

import dataclasses
import logging
from typing import Dict, Optional, Type

from dbgpt.configs.model_config import get_device
from dbgpt.core import ModelOutput
from dbgpt.model.adapter.base import ConversationAdapter, LLMModelAdapter
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import ModelParameters

logger = logging.getLogger(__name__)
try:
    from llama_cpp_server_py_core import (
        ChatCompletionRequest,
        ChatCompletionStreamResponse,  # noqa: F401
        CompletionRequest,
        CompletionResponse,  # noqa: F401
        LlamaCppServer,
        ServerConfig,
        ServerProcess,
    )
except ImportError:
    logger.error(
        "Failed to import llama_cpp_server_py_core, please install it first by "
        "`pip install llama-cpp-server-py-core`"
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
        device = self.device or get_device()
        if device and device == "cuda" and not self.n_gpu_layers:
            # Set n_gpu_layers to a large number to use all layers
            logger.info("Set n_gpu_layers to a large number to use all layers")
            self.n_gpu_layers = 1000000000


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

    def support_generate_function(self) -> bool:
        return True

    def get_generate_stream_function(self, model, model_path: str):
        return generate_stream

    def get_generate_function(self, model, model_path: str):
        return generate


def generate_stream(
    model: LlamaCppServer,
    tokenizer: LlamaCppServer,
    params: Dict,
    device: str,
    context_len: int,
):
    chat_model = params.get("chat_model", True)
    if chat_model is None:
        chat_model = True
    if chat_model:
        for out in chat_generate_stream(model, params):
            yield out
    else:
        req = _build_completion_request(params, stream=True)
        # resp = model.stream_completion(req)
        text = ""
        for r in model.stream_completion(req):
            text += r.content
            timings = r.timings
            usage = {
                "completion_tokens": r.tokens_predicted,
                "prompt_tokens": r.tokens_evaluated,
                "total_tokens": r.tokens_predicted + r.tokens_evaluated,
            }
            if timings:
                logger.debug(f"Timings: {timings}")
            yield ModelOutput(
                text=text,
                error_code=0,
                finish_reason=_parse_finish_reason(r.stop_type),
                usage=usage,
            )


def chat_generate_stream(
    model: LlamaCppServer,
    params: Dict,
):
    req = _build_chat_completion_request(params, stream=True)
    text = ""
    for r in model.stream_chat_completion(req):
        if len(r.choices) == 0:
            continue
        # Check for empty 'choices' issue in Azure GPT-4o responses
        if r.choices[0] is not None and r.choices[0].delta is None:
            continue
        content = r.choices[0].delta.content
        finish_reason = _parse_finish_reason(r.choices[0].finish_reason)

        if content is not None:
            content = r.choices[0].delta.content
            text += content
            yield ModelOutput(
                text=text, error_code=0, finish_reason=finish_reason, usage=r.usage
            )
        elif text and content is None:
            # Last response is empty, return the text
            yield ModelOutput(
                text=text, error_code=0, finish_reason=finish_reason, usage=r.usage
            )


def _build_chat_completion_request(
    params: Dict, stream: bool = True
) -> ChatCompletionRequest:
    from dbgpt.model.proxy.llms.proxy_model import parse_model_request

    # LLamaCppServer does not need to parse the model
    model_request = parse_model_request(params, "", stream=stream)
    return ChatCompletionRequest(
        messages=model_request.to_common_messages(),
        temperature=params.get("temperature"),
        top_p=params.get("top_p"),
        top_k=params.get("top_k"),
        max_tokens=params.get("max_new_tokens"),
        stop=params.get("stop"),
        stream=stream,
        presence_penalty=params.get("presence_penalty"),
        frequency_penalty=params.get("frequency_penalty"),
        user=params.get("user_name"),
    )


def _build_completion_request(params: Dict, stream: bool = True) -> CompletionRequest:
    from dbgpt.model.proxy.llms.proxy_model import parse_model_request

    # LLamaCppServer does not need to parse the model
    model_request = parse_model_request(params, "", stream=stream)
    prompt = params.get("prompt")
    if not prompt and model_request.messages:
        prompt = model_request.messages[-1].content
    if not prompt:
        raise ValueError("Prompt is required for non-chat model")

    return CompletionRequest(
        prompt=prompt,
        temperature=params.get("temperature"),
        top_p=params.get("top_p"),
        top_k=params.get("top_k"),
        n_predict=params.get("max_new_tokens"),
        stop=params.get("stop"),
        stream=stream,
        presence_penalty=params.get("presence_penalty"),
        frequency_penalty=params.get("frequency_penalty"),
    )


def generate(
    model: LlamaCppServer,
    tokenizer: LlamaCppServer,
    params: Dict,
    device: str,
    context_len: int,
):
    chat_model = params.get("chat_model", True)
    if chat_model is None:
        chat_model = True

    if chat_model:
        req = _build_chat_completion_request(params, stream=False)
        resp = model.chat_completion(req)
        if not resp.choices or not resp.choices[0].message:
            raise ValueError("Response can't be empty")
        content = resp.choices[0].message.content
        return ModelOutput(
            text=content,
            error_code=0,
            finish_reason=_parse_finish_reason(resp.choices[0].finish_reason),
            usage=resp.usage,
        )

    else:
        req = _build_completion_request(params, stream=False)
        resp = model.completion(req)
        content = resp.content
        usage = {
            "completion_tokens": resp.tokens_predicted,
            "prompt_tokens": resp.tokens_evaluated,
            "total_tokens": resp.tokens_predicted + resp.tokens_evaluated,
        }
        return ModelOutput(
            text=content,
            error_code=0,
            finish_reason=_parse_finish_reason(resp.stop_type),
            usage=usage,
        )


def _parse_finish_reason(finish_reason: Optional[str]) -> Optional[str]:
    if finish_reason == "limit":
        return "length"
    elif finish_reason is not None:
        return "stop"
    return None
