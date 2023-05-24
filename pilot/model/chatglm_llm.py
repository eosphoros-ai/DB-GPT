#!/usr/bin/env python3
# -*- coding:utf-8 -*-

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
    hist = []

    messages = prompt.split(stop)

    # Add history chat to hist for model.
    for i in range(1, len(messages) - 2, 2):
        hist.append(
            (
                messages[i].split(ROLE_USER + ":")[1],
                messages[i + 1].split(ROLE_ASSISTANT + ":")[1],
            )
        )

    query = messages[-2].split(ROLE_USER + ":")[1]
    print("Query Message: ", query)
    output = ""
    i = 0
    for i, (response, new_hist) in enumerate(
        model.stream_chat(tokenizer, query, hist, **generate_kwargs)
    ):
        if echo:
            output = query + " " + response
        else:
            output = response

        yield output

    yield output
