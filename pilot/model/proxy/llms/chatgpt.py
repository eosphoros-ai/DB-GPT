#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from typing import List

import openai

from pilot.model.proxy.llms.proxy_model import ProxyModel
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType


def chatgpt_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    history = []

    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    proxy_api_key = model_params.proxy_api_key
    openai.api_key = openai_key = os.getenv("OPENAI_API_KEY") or proxy_api_key
    proxyllm_backend = model_params.proxyllm_backend
    if not proxyllm_backend:
        proxyllm_backend = "gpt-3.5-turbo"

    messages: List[ModelMessage] = params["messages"]
    # Add history conversation
    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "system", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
        else:
            pass

    # Move the last user's information to the end
    temp_his = history[::-1]
    last_user_input = None
    for m in temp_his:
        if m["role"] == "user":
            last_user_input = m
            break
    if last_user_input:
        history.remove(last_user_input)
        history.append(last_user_input)

    payloads = {
        "model": proxyllm_backend,  # just for test, remove this later
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_new_tokens"),
        "stream": True,
    }
    res = openai.ChatCompletion.create(messages=history, **payloads)

    print(f"Send request to real model {proxyllm_backend}")

    text = ""
    for r in res:
        if r["choices"][0]["delta"].get("content") is not None:
            content = r["choices"][0]["delta"]["content"]
            text += content
            yield text
