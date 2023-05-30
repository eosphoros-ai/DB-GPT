#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
from pilot.configs.config import Config
from pilot.conversation import ROLE_ASSISTANT, ROLE_USER

CFG = Config()

def proxyllm_generate_stream(
    model, tokenizer, params, device, context_len=2048
):

    history = []

    prompt = params["prompt"]
    stop = params.get("stop", "###")

    headers = {
        "Authorization": "Bearer " + CFG.proxy_api_key
    }
  
    messages = prompt.split(stop)

    # Add history conversation
    for i in range(1, len(messages) - 2, 2):
        history.append(
            {"role": "user", "content": messages[i].split(ROLE_USER + ":")[1]},
        )
        history.append(
            {"role": "system", "content": messages[i + 1].split(ROLE_ASSISTANT + ":")[1]}
        )
    
    # Add user query 
    query = messages[-2].split(ROLE_USER + ":")[1]
    history.append(
        {"role": "user", "content": query}
    )
    payloads = {
        "model": "gpt-3.5-turbo",   # just for test, remove this later
        "messages": history, 
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_new_tokens"),
    }

    res = requests.post(CFG.proxy_server_url, headers=headers, json=payloads, stream=True)

    text = ""
    for line in res.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            json_line = json.loads(decoded_line)
            print(json_line)
            text += json_line["choices"][0]["message"]["content"]
            yield text 