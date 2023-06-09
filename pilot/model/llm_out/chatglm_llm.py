#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import copy

import torch

from pilot.conversation import ROLE_ASSISTANT, ROLE_USER


@torch.inference_mode()
def chatglm_generate_stream(
    model, tokenizer, params, device, context_len=2048, stream_interval=2
):
    """Generate text using chatglm model's chat api"""
    prompt = params["prompt"]
    temperature = float(params.get("temperature", 1.0))
    top_p = float(params.get("top_p", 1.0))
    stop = params.get("stop", "###")
    echo = params.get("echo", False)

    generate_kwargs = {
        "do_sample": True if temperature > 1e-5 else False,
        "top_p": top_p,
        "repetition_penalty": 1.0,
        "logits_processor": None,
    }

    if temperature > 1e-5:
        generate_kwargs["temperature"] = temperature

    # TODO, Fix this
    print(prompt)
    messages = prompt.split(stop)
    #
    # # Add history conversation
    hist = []
    once_conversation = []
    for message in messages[:-2]:
        if len(message) <= 0:
            continue

        if "human:" in message:
            once_conversation.append(message.split("human:")[1])
        # elif "system:" in message:
        #     once_conversation.append(f"""###system:{message.split("system:")[1]} """)
        elif "ai:" in message:
            once_conversation.append(message.split("ai:")[1])
            last_conversation = copy.deepcopy(once_conversation)
            hist.append(last_conversation)
            once_conversation = []
        # else:
        #     once_conversation.append(f"""###system:{message} """)

    try:
        query = messages[-2].split("human:")[1]
    except IndexError:
        query = messages[-3].split("human:")[1]
    print("Query Message: ", query)
    # output = ""
    # i = 0

    for i, (response, new_hist) in enumerate(
        model.stream_chat(tokenizer, query, hist, **generate_kwargs)
    ):
        if echo:
            output = query + " " + response
        else:
            output = response

        yield output

    yield output
