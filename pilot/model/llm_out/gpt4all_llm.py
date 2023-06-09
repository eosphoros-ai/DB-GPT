#!/usr/bin/env python3
# -*- coding:utf-8 -*-

def gpt4all_generate_stream(model, tokenizer, params, device, max_position_embeddings):
    stop = params.get("stop", "###")
    prompt = params["prompt"]
    role, query = prompt.split(stop)[1].split(":")
    print(f"gpt4all, role: {role}, query: {query}")

    messages = [{"role": "user", "content": query}]
    res = model.chat_completion(messages)
    if res.get('choices') and len(res.get('choices')) > 0 and res.get('choices')[0].get('message') and \
            res.get('choices')[0].get('message').get('content'):
        yield res.get('choices')[0].get('message').get('content')
    else:
        yield "error response"

