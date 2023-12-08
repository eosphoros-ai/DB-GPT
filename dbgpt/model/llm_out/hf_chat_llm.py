import logging
import torch
from threading import Thread
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
    generate_kwargs = {
        "input_ids": input_ids,
        "max_length": context_len,
        "temperature": temperature,
        "streamer": streamer,
    }

    thread = Thread(target=model.generate, kwargs=generate_kwargs)
    thread.start()
    out = ""
    for new_text in streamer:
        out += new_text
        yield out
