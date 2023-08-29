#!/usr/bin/env python3
# -*- coding:utf-8 -*-


def gpt4all_generate_stream(model, tokenizer, params, device, max_position_embeddings):
    stop = params.get("stop", "###")
    prompt = params["prompt"]
    role, query = prompt.split(stop)[0].split(":")
    print(f"gpt4all, role: {role}, query: {query}")
    yield model.generate(prompt=query, streaming=True)
