import logging
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

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
    do_sample = params.get("do_sample", None)
    custom_stop_words = params.get("custom_stop_words", [])

    input_ids = tokenizer(prompt).input_ids
    # input_ids = input_ids.to(device)
    if model.config.is_encoder_decoder:
        max_src_len = context_len
    else:  # truncate
        max_src_len = context_len - max_new_tokens - 1
    input_ids = input_ids[-max_src_len:]
    input_echo_len = len(input_ids)
    input_ids = torch.as_tensor([input_ids], device=device)

    # messages = params["messages"]
    # messages = ModelMessage.to_openai_messages(messages)
    # input_ids = tokenizer.apply_chat_template(conversation=messages, tokenize=True, add_generation_prompt=True, return_tensors='pt')
    # input_ids = input_ids.to(device)

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

    logger.info(f"Predict with parameters: {base_kwargs}")

    generate_kwargs = {"input_ids": input_ids, **base_kwargs}
    thread = Thread(target=model.generate, kwargs=generate_kwargs)
    thread.start()
    out = ""
    for new_text in streamer:
        out += new_text
        if custom_stop_words:
            for stop_word in custom_stop_words:
                if out.endswith(stop_word):
                    out = out[: -len(stop_word)]
        yield out
