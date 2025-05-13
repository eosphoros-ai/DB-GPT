import logging
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from dbgpt.core import ModelOutput

from ...utils.hf_stream_utils import PerformanceMonitoringStreamer
from ...utils.parse_utils import (
    _DEFAULT_THINK_END_TOKEN,
    _DEFAULT_THINK_START_TOKEN,
    ParsedChatMessage,
    parse_chat_message,
)

logger = logging.getLogger(__name__)


@torch.inference_mode()
def huggingface_chat_generate_stream(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    params,
    device,
    context_len=4096,
):
    prompt = params["prompt"]
    temperature = float(params.get("temperature", 0.7))
    top_p = float(params.get("top_p", 1.0))
    echo = params.get("echo", False)
    max_new_tokens = int(params.get("max_new_tokens", 4096))
    stop_token_ids = params.get("stop_token_ids", [])
    do_sample = params.get("do_sample", True)
    custom_stop_words = params.get("custom_stop_words", [])
    think_start_token = params.get("think_start_token", _DEFAULT_THINK_START_TOKEN)
    think_end_token = params.get("think_end_token", _DEFAULT_THINK_END_TOKEN)
    is_reasoning_model = params.get("is_reasoning_model", False)
    use_cache = params.get("use_cache", True)
    cache_implementation = params.get("cache_implementation")
    reasoning_patterns = [
        {"start": think_start_token, "end": think_end_token},
    ]

    audios = params.get("audios")
    images = params.get("images")
    videos = params.get("videos")
    has_media = True if audios or images or videos else False
    token_kwargs = {"text": [prompt], "return_tensors": "pt"}
    if audios:
        token_kwargs["audio"] = audios
    if images:
        token_kwargs["images"] = images
    if videos:
        token_kwargs["videos"] = videos
    if has_media:
        token_kwargs["padding"] = True
    tokenize_results = tokenizer(**token_kwargs)
    input_token_count = tokenize_results.input_ids.shape[1]  # Count input tokens
    tokenize_results = tokenize_results.to(device)
    #
    # if model.config.is_encoder_decoder:
    #     max_src_len = context_len
    # else:  # truncate
    #     max_src_len = context_len - max_new_tokens - 1
    # input_ids = tokenizer(prompt).input_ids
    # input_ids = input_ids[-max_src_len:]
    # # input_echo_len = len(input_ids)
    # input_ids = torch.as_tensor([input_ids], device=device)

    streamer = PerformanceMonitoringStreamer(
        tokenizer,
        skip_prompt=not echo,
        skip_special_tokens=True,
        input_token_count=input_token_count,
    )

    base_kwargs = {
        "temperature": temperature,
        "streamer": streamer,
        "top_p": top_p,
        "use_cache": use_cache,
        "max_new_tokens": max_new_tokens,
    }

    if stop_token_ids:
        base_kwargs["eos_token_id"] = stop_token_ids
    if do_sample is not None:
        base_kwargs["do_sample"] = do_sample
    if cache_implementation:
        base_kwargs["cache_implementation"] = cache_implementation

    logger.info(
        f"Predict with parameters: {base_kwargs}\ncustom_stop_words: "
        f"{custom_stop_words}"
    )
    generate_kwargs = {**tokenize_results, **base_kwargs}

    def generate_with_resilience():
        try:
            _outputs = model.generate(**generate_kwargs, return_dict_in_generate=True)
        except torch.cuda.OutOfMemoryError as e:
            logger.warning(
                f"OOM error occurred: {e}. Trying cleanup and retrying generation."
            )
            torch.cuda.empty_cache()
            model.generate(**generate_kwargs)
        except Exception as ex:
            logger.error(f"Unexpected error during generation: {ex}")
            streamer.end()
            raise

    streamer.start_prefill()
    thread = Thread(target=generate_with_resilience)
    thread.start()
    text = ""
    usage = None
    msg = ParsedChatMessage()
    is_first = True
    for new_text in streamer:
        text += new_text
        if custom_stop_words:
            for stop_word in custom_stop_words:
                if text.endswith(stop_word):
                    text = text[: -len(stop_word)]

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
        perf_metrics = streamer.get_performance_metrics()
        usage = {
            "prompt_tokens": perf_metrics["input_token_count"],
            "completion_tokens": perf_metrics["total_tokens_generated"],
            "total_tokens": perf_metrics["input_token_count"]
            + perf_metrics["total_tokens_generated"],
        }
        usage.update(perf_metrics)

        yield ModelOutput.build(
            msg.content,
            msg.reasoning_content,
            error_code=0,
            usage=usage,
            is_reasoning_model=is_reasoning_model,
        )
    thread.join()
