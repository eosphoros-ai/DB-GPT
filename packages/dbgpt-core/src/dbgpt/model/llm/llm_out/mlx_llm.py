from typing import Dict

import mlx.nn as nn
from mlx_lm import stream_generate
from mlx_lm.sample_utils import make_sampler
from mlx_lm.tokenizer_utils import TokenizerWrapper

from dbgpt.core import ModelOutput

from ...utils.llm_metrics import LLMPerformanceMonitor
from ...utils.parse_utils import (
    _DEFAULT_THINK_END_TOKEN,
    _DEFAULT_THINK_START_TOKEN,
    parse_chat_message,
)


def generate_stream(
    model: nn.Module,
    tokenizer: TokenizerWrapper,
    params: Dict,
    device: str,
    context_len: int,
):
    prompt = params["prompt"]
    temperature = float(params.get("temperature", 0))
    top_p = float(params.get("top_p", 1.0))
    top_k = params.get("top_k", 0)
    max_new_tokens = int(params.get("max_new_tokens", 2048))
    # echo = bool(params.get("echo", True))
    think_start_token = params.get("think_start_token", _DEFAULT_THINK_START_TOKEN)
    think_end_token = params.get("think_end_token", _DEFAULT_THINK_END_TOKEN)
    is_reasoning_model = params.get("is_reasoning_model", False)

    reasoning_patterns = [
        {"start": think_start_token, "end": think_end_token},
    ]
    sampler = make_sampler(
        temp=temperature,
        top_p=top_p,
        # min_p=min_p,
        # min_tokens_to_keep=min_tokens_to_keep,
        top_k=top_k,
        xtc_special_tokens=tokenizer.encode("\n") + list(tokenizer.eos_token_ids),
    )

    # Initialize the performance monitor with estimated token count
    estimated_input_tokens = len(tokenizer.encode(prompt))
    perf_monitor = LLMPerformanceMonitor(input_token_count=estimated_input_tokens)

    # Start measuring prefill phase
    perf_monitor.start_prefill()

    results_generator = stream_generate(
        model, tokenizer, prompt=prompt, max_tokens=max_new_tokens, sampler=sampler
    )
    text = ""
    is_first = True
    for res in results_generator:
        new_text = res.text
        text += new_text
        # The prompt processing tokens-per-second.
        # prompt_tps = res.prompt_tps
        # The number of tokens in the prompt.
        prompt_tokens = res.prompt_tokens
        # The number of generated tokens.
        generation_tokens = res.generation_tokens
        # The tokens-per-second for generation.
        # generation_tps = res.generation_tps
        # The peak memory used so far in GB.
        # peak_memory = res.peak_memory
        # "length", "stop" or `None`
        finish_reason = res.finish_reason
        if (
            prompt.rstrip().endswith(think_start_token)
            and is_reasoning_model
            and is_first
        ):
            text = think_start_token + "\n" + text
            is_first = False

        msg = parse_chat_message(
            text,
            extract_reasoning=is_reasoning_model,
            reasoning_patterns=reasoning_patterns,
        )

        # If this is the first iteration, update the input token count
        if perf_monitor.metrics.input_token_count != prompt_tokens:
            perf_monitor.metrics.input_token_count = prompt_tokens
        # Update performance metrics based on current token count
        perf_metrics = perf_monitor.on_tokens_received(generation_tokens)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": generation_tokens,
            "total_tokens": prompt_tokens + generation_tokens,
        }
        # Check if generation is complete
        is_complete = finish_reason is not None
        if is_complete:
            perf_monitor.end_generation()
        usage.update(perf_metrics)

        yield ModelOutput.build(
            msg.content,
            msg.reasoning_content,
            error_code=0,
            usage=usage,
            is_reasoning_model=is_reasoning_model,
        )
