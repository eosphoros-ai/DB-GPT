#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
from pilot.configs.config import Config
from pilot.conversation import ROLE_ASSISTANT, ROLE_USER

CFG = Config()


def proxyllm_generate_stream(model, tokenizer, params, device, context_len=2048):
    history = []

    prompt = params["prompt"]
    stop = params.get("stop", "###")

    headers = {
        "Authorization": "Bearer " + CFG.proxy_api_key,
        "Token": CFG.proxy_api_key,
    }

    messages = prompt.split(stop)
    # Add history conversation
    for message in messages:
        if len(message) <= 0:
            continue
        if "human:" in message:
            history.append(
                {"role": "user", "content": message.split("human:")[1]},
            )
        elif "system:" in message:
            history.append(
                {
                    "role": "system",
                    "content": message.split("system:")[1],
                }
            )
        elif "ai:" in message:
            history.append(
                {
                    "role": "ai",
                    "content": message.split("ai:")[1],
                }
            )
        else:
            history.append(
                {
                    "role": "system",
                    "content": message,
                }
            )

    # Move the last user's information to the end
    temp_his = history[::-1]
    last_user_input = None
    for m in temp_his:
        if m["role"] == "user":
            last_user_input = m
    if last_user_input:
        history.remove(last_user_input)
        history.append(last_user_input)

    payloads = {
        "model": "gpt-3.5-turbo",  # just for test, remove this later
        "messages": history,
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_new_tokens"),
        "stream": True,
    }

    res = requests.post(
        CFG.proxy_server_url, headers=headers, json=payloads, stream=True
    )

    text = ""
    for line in res.iter_lines():
        if line:
            json_data = line.split(b": ", 1)[1]
            decoded_line = json_data.decode("utf-8")
            if decoded_line.lower() != "[DONE]".lower():
                obj = json.loads(json_data)
                if obj["choices"][0]["delta"].get("content") is not None:
                    content = obj["choices"][0]["delta"]["content"]
                    text += content
            yield text
