import logging
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from dbgpt.core import ModelOutput

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
    max_new_tokens = int(params.get("max_new_tokens", 2048))
    stop_token_ids = params.get("stop_token_ids", [])
    do_sample = params.get("do_sample", True)
    custom_stop_words = params.get("custom_stop_words", [])

    input_ids = tokenizer(prompt).input_ids
    # input_ids = input_ids.to(device)
    if model.config.is_encoder_decoder:
        max_src_len = context_len
    else:  # truncate
        max_src_len = context_len - max_new_tokens - 1
    input_ids = input_ids[-max_src_len:]
    # input_echo_len = len(input_ids)
    input_ids = torch.as_tensor([input_ids], device=device)

    streamer = TextIteratorStreamer(
        tokenizer, skip_prompt=not echo, skip_special_tokens=True
    )

    base_kwargs = {
        "max_length": context_len,
        "temperature": temperature,
        "streamer": streamer,
        "top_p": top_p,
    }

    if stop_token_ids:
        base_kwargs["eos_token_id"] = stop_token_ids
    if do_sample is not None:
        base_kwargs["do_sample"] = do_sample

    logger.info(
        f"Predict with parameters: {base_kwargs}\ncustom_stop_words: "
        f"{custom_stop_words}"
    )

    generate_kwargs = {"input_ids": input_ids, **base_kwargs}
    thread = Thread(target=model.generate, kwargs=generate_kwargs)
    thread.start()
    reasoning_content = ""
    text = ""
    usage = None
    if "r1" in params["model"] or "reasoner" in params["model"]:
        is_thinking = True
    else:
        is_thinking = False

    for new_text in streamer:
        if is_thinking:
            reasoning_content += new_text
            if "</think>" in reasoning_content:
                parts = reasoning_content.split("</think>")
                reasoning_content = parts[0]
                text = parts[1]
                is_thinking = False
        else:
            text += new_text
        if custom_stop_words:
            for stop_word in custom_stop_words:
                if text.endswith(stop_word):
                    text = text[: -len(stop_word)]
        yield ModelOutput.build(text, reasoning_content, usage=usage)
