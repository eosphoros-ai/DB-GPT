#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
import time
import gradio as gr
import datetime

from pilot.configs.model_config import LOGDIR

from pilot.conversation import (
    get_default_conv_template,
    compute_skip_echo_len,
    SeparatorStyle
)

from fastchat.utils import (
    build_logger,
    server_error_msg,
    violates_moderation,
    moderation_msg
)

from fastchat.serve.gradio_patch import Chatbot as grChatbot
from fastchat.serve.gradio_css import code_highlight_css

logger = build_logger("webserver", "webserver.log")
headers = {"User-Agent": "dbgpt Client"}

no_change_btn = gr.Button.update()
enable_btn = gr.Button.update(interactive=True)
disable_btn = gr.Button.update(interactive=True)

enable_moderation = False
models = []

priority = {
    "vicuna-13b": "aaa"
}

def set_global_vars(enable_moderation_, models_):
    global enable_moderation, models
    enable_moderation = enable_moderation_
    models = models_

def get_conv_log_filename():
    t = datetime.datetime.now()
    name = os.path.join(LOGDIR, f"{t.year}-{t.month:02d}-{t.day:02d}-conv.json")
    return name


def regenerate(state, request: gr.Request):
    logger.info(f"regenerate. ip: {request.client.host}")
    state.messages[-1][-1] = None
    state.skip_next = False
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5

def clear_history(request: gr.Request):
    logger.info(f"clear_history. ip: {request.client.host}")
    state = None
    return (state, [], "") + (disable_btn,) * 5

def add_text(state, text, request: gr.Request):
    logger.info(f"add_text. ip: {request.client.host}. len:{len(text)}")

    if state is None:
        state = get_default_conv_template("vicuna").copy()
    
    if len(text) <= 0:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), "") + (no_change_btn,) * 5
    
    if enable_moderation:
        flagged = violates_moderation(text)
        if flagged:
            logger.info(f"violate moderation. ip: {request.client.host}. text: {text}")
            state.skip_next = True
            return (state, state.to_gradio_chatbot(), moderation_msg) + (no_change_btn,) * 5
    text = text[:1536]  # ? 
    state.append_message(state.roles[0], text)      
    state.append_message(state.roles[1], None)
    state.skip_next = False

    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5

def post_process_code(code):
    sep = "\n```"
    if sep in code:
        blocks = code.split(sep)
        if len(blocks) % 2 == 1:
            for i in range(1, len(blocks), 2):
                blocks[i] = blocks[i].replace("\\_", "_")
        code = sep.join(blocks)
    return code

def http_bot(state, model_selector, temperature, max_new_tokens, request: gr.Request):
    logger.info(f"http_bot. ip: {request.client.host}")
    start_tstamp = time.time()

    model_name = model_selector
    temperature = float(temperature)
    max_new_tokens = int(max_new_tokens)

    if state.skip_next:
        yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
        return

    if len(state.message) == state.offset + 2:
        new_state = get_default_conv_template(model_name).copy()
        new_state.conv_id = uuid.uuid4().hex
        new_state.append_message(new_state.roles[0], state.messages[-2][1])
        new_state.append_message(new_state.roles[1], None)
        state = new_state


    # TODO 