import os
from typing import Dict

from vllm import AsyncLLMEngine
from vllm.sampling_params import SamplingParams
from vllm.utils import random_uuid

from dbgpt.core import ModelOutput

from ...utils.parse_utils import _DEFAULT_THINK_START_TOKEN, parse_chat_message

_IS_BENCHMARK = os.getenv("DB_GPT_MODEL_BENCHMARK", "False").lower() == "true"


async def generate_stream(
    model: AsyncLLMEngine, tokenizer, params: Dict, device: str, context_len: int
):
    """
    Adapted from https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/vllm_worker.py
    """
    prompt = params["prompt"]
    request_id = params.pop("request_id") if "request_id" in params else random_uuid()
    temperature = float(params.get("temperature", 1.0))
    top_p = float(params.get("top_p", 1.0))
    top_k = params.get("top_k", -1)
    presence_penalty = float(params.get("presence_penalty", 0.0))
    frequency_penalty = float(params.get("frequency_penalty", 0.0))
    max_new_tokens = int(params.get("max_new_tokens", 2048))
    echo = bool(params.get("echo", True))
    # use_beam_search = params.get("use_beam_search", False)
    best_of = params.get("best_of", None)
    stop_str = params.get("stop", None)
    think_start_token = params.get("think_start_token", _DEFAULT_THINK_START_TOKEN)
    is_reasoning_model = params.get("is_reasoning_model", False)
    # think_end_token = params.get("think_end_token", _DEFAULT_THINK_END_TOKEN)

    stop_token_ids = params.get("stop_token_ids", None) or []
    if tokenizer.eos_token_id is not None:
        stop_token_ids.append(tokenizer.eos_token_id)

    # Handle stop_str
    stop = set()
    if isinstance(stop_str, str) and stop_str != "":
        stop.add(stop_str)
    elif isinstance(stop_str, list) and stop_str != []:
        stop.update(stop_str)

    for tid in stop_token_ids:
        if tid is not None:
            stop.add(tokenizer.decode(tid))

    # make sampling params in vllm
    top_p = max(top_p, 1e-5)
    if temperature <= 1e-5:
        top_p = 1.0
    gen_params = {
        "stop": list(stop),
        "ignore_eos": False,
    }
    prompt_token_ids = None
    if _IS_BENCHMARK:
        gen_params["stop"] = []
        gen_params["ignore_eos"] = True
        prompt_len = context_len - max_new_tokens - 2
        prompt_token_ids = tokenizer([prompt]).input_ids[0]
        prompt_token_ids = prompt_token_ids[-prompt_len:]
    sampling_params = SamplingParams(
        n=1,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_new_tokens,
        top_k=top_k,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        best_of=best_of,
        **gen_params,
    )
    # vocab = tokenizer.get_vocab()

    results_generator = model.generate(prompt, sampling_params, request_id)
    usage = None
    finish_reason = None
    async for request_output in results_generator:
        prompt = request_output.prompt
        if echo:
            text_outputs = [prompt + output.text for output in request_output.outputs]
        else:
            text_outputs = [output.text for output in request_output.outputs]
        text_outputs = " ".join(text_outputs)

        # Note: usage is not supported yet
        prompt_tokens = len(request_output.prompt_token_ids)
        completion_tokens = sum(
            len(output.token_ids) for output in request_output.outputs
        )
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        finish_reason = (
            request_output.outputs[0].finish_reason
            if len(request_output.outputs) == 1
            else [output.finish_reason for output in request_output.outputs]
        )
        if text_outputs:
            # Tempora
            if prompt.rstrip().endswith(think_start_token) and is_reasoning_model:
                text_outputs = think_start_token + "\n" + text_outputs
            msg = parse_chat_message(
                text_outputs,
                extract_reasoning=is_reasoning_model,
            )
            yield ModelOutput.build(
                msg.content,
                msg.reasoning_content,
                error_code=0,
                usage=usage,
                finish_reason=finish_reason,
                is_reasoning_model=is_reasoning_model,
            )
