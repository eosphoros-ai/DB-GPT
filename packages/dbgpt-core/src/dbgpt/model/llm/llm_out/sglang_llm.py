import os
from typing import Dict

from sglang.srt.entrypoints.engine import Engine as AsyncLLMEngine
from sglang.srt.sampling.sampling_params import SamplingParams

from dbgpt.core import ModelOutput

_IS_BENCHMARK = os.getenv("DB_GPT_MODEL_BENCHMARK", "False").lower() == "true"


async def generate_stream(
    model: AsyncLLMEngine, tokenizer, params: Dict, device: str, content_length: int
):
    prompt = params["prompt"]
    temperature = float(params.get("temperature", 1.0))
    top_p = float(params.get("top_p", 1.0))
    top_k = params.get("top_k", -1.0)
    frequency_penalty = float(params.get("frequency_penalty", 0.0))
    presence_penalty = float(params.get("presence_penalty", 0.0))
    max_new_tokens = int(params.get("max_new_tokens", 32768))
    stop_str = params.get("stop", None)
    stop_token_ids = params.get("stop_token_ids", None) or []
    echo = params.get("echo", True)

    # Handle stop_str
    stop = []
    if isinstance(stop_str, str) and stop_str != "":
        stop.append(stop_str)
    elif isinstance(stop_str, list) and stop_str != []:
        stop.extend(stop_str)

    for tid in stop_token_ids:
        s = tokenizer.decode(tid)
        if s != "":
            stop.append(s)

    # make sampling params for sgl.gen
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
        prompt_len = content_length - max_new_tokens - 2
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
        **gen_params,
    )

    results_generator = model.async_generate(prompt, sampling_params, stream=True)
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

        yield ModelOutput(
            text=text_outputs,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            usage=usage,
            finish_reason=finish_reason,
        )
