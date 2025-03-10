"""llama.cpp server adapter.

See more details:
https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md

**Features:**
 * LLM inference of F16 and quantized models on GPU and CPU
 * Parallel decoding with multi-user support
 * Continuous batching

The llama.cpp server is pure C++ server, we need to use the llama-cpp-server-py
to interact with it.
"""

import logging
from typing import Dict, Optional

from dbgpt.core import ModelOutput

from ...utils.parse_utils import (
    _DEFAULT_THINK_START_TOKEN,
    ParsedChatMessage,
    parse_chat_message,
)

logger = logging.getLogger(__name__)

try:
    from llama_cpp_server_py_core import (
        ChatCompletionRequest,
        ChatCompletionStreamResponse,  # noqa: F401
        CompletionRequest,
        CompletionResponse,  # noqa: F401
        LlamaCppServer,
    )
except ImportError:
    logger.error(
        "Failed to import llama_cpp_server_py_core, please install it first by "
        "`pip install llama-cpp-server-py`"
    )
    raise


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
    think_start_token = params.get("think_start_token", _DEFAULT_THINK_START_TOKEN)
    is_reasoning_model = params.get("is_reasoning_model", False)
    msg = ParsedChatMessage()
    is_first = True
    for r in model.stream_chat_completion(req):
        if len(r.choices) == 0:
            continue
        # Check for empty 'choices' issue in Azure GPT-4o responses
        if r.choices[0] is not None and r.choices[0].delta is None:
            continue
        content = r.choices[0].delta.content
        if content is None:
            continue

        text += content
        if is_reasoning_model and not text.startswith(think_start_token) and is_first:
            text = think_start_token + "\n" + text
            is_first = False

        msg = parse_chat_message(text, extract_reasoning=is_reasoning_model)
        finish_reason = _parse_finish_reason(r.choices[0].finish_reason)

        yield ModelOutput.build(
            msg.content,
            msg.reasoning_content,
            error_code=0,
            finish_reason=finish_reason,
            usage=r.usage,
            is_reasoning_model=is_reasoning_model,
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
        msg = parse_chat_message(content, extract_reasoning=True)
        return ModelOutput.build(
            msg.content,
            msg.reasoning_content,
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
