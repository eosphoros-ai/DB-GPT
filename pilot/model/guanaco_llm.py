#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
import transformers
from transformers import GenerationConfig
from pilot.model.llm_utils import Iteratorize, Stream


def guanaco_generate_output(model, tokenizer, params, device):
    """Fork from fastchat: https://github.com/KohakuBlueleaf/guanaco-lora/blob/main/generate.py"""
    prompt = params["prompt"]
    inputs = tokenizer(prompt, return_tensors="pt")
    input_ids = inputs["input_ids"].to(device)
    temperature = (0.5,)
    top_p = (0.95,)
    top_k = (45,)
    max_new_tokens = (128,)
    stream_output = True

    generation_config = GenerationConfig(
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
    )

    generate_params = {
        "input_ids": input_ids,
        "generation_config": generation_config,
        "return_dict_in_generate": True,
        "output_scores": True,
        "max_new_tokens": max_new_tokens,
    }

    if stream_output:
        # Stream the reply 1 token at a time.
        # This is based on the trick of using 'stopping_criteria' to create an iterator,
        # from https://github.com/oobabooga/text-generation-webui/blob/ad37f396fc8bcbab90e11ecf17c56c97bfbd4a9c/modules/text_generation.py#L216-L243.

        def generate_with_callback(callback=None, **kwargs):
            kwargs.setdefault("stopping_criteria", transformers.StoppingCriteriaList())
            kwargs["stopping_criteria"].append(Stream(callback_func=callback))
            with torch.no_grad():
                model.generate(**kwargs)

        def generate_with_streaming(**kwargs):
            return Iteratorize(generate_with_callback, kwargs, callback=None)

        with generate_with_streaming(**generate_params) as generator:
            for output in generator:
                # new_tokens = len(output) - len(input_ids[0])
                decoded_output = tokenizer.decode(output)

                if output[-1] in [tokenizer.eos_token_id]:
                    break

                yield decoded_output.split("### Response:")[-1].strip()
        return  # early return for stream_output

    with torch.no_grad():
        generation_output = model.generate(
            input_ids=input_ids,
            generation_config=generation_config,
            return_dict_in_generate=True,
            output_scores=True,
            max_new_tokens=max_new_tokens,
        )

    s = generation_output.sequences[0]
    print(f"debug_sequences,{s}", s)
    output = tokenizer.decode(s)
    print(f"debug_output,{output}", output)
    yield output.split("### Response:")[-1].strip()
