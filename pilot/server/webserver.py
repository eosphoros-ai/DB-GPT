#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import uuid
import json
import time
import gradio as gr
import datetime
import requests
from urllib.parse import urljoin

from pilot.configs.model_config import LOGDIR, vicuna_model_server, LLM_MODEL

from pilot.conversation import (
    default_conversation,
    conv_templates,
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

get_window_url_params = """
function() {
    const params = new URLSearchParams(window.location.search);
    url_params = Object.fromEntries(params);
    console.log(url_params);
    gradioURL = window.location.href
    if (!gradioURL.endsWith('?__theme=dark')) {
        window.location.replace(gradioURL + '?__theme=dark');
    }
    return url_params;
    }
"""
def load_demo(url_params, request: gr.Request):
    logger.info(f"load_demo. ip: {request.client.host}. params: {url_params}")

    dropdown_update = gr.Dropdown.update(visible=True)
    if "model" in url_params:
        model = url_params["model"]
        if model in models:
            dropdown_update = gr.Dropdown.update(
                value=model, visible=True)

    state = default_conversation.copy()
    return (state,
            dropdown_update,
            gr.Chatbot.update(visible=True),
            gr.Textbox.update(visible=True),
            gr.Button.update(visible=True),
            gr.Row.update(visible=True),
            gr.Accordion.update(visible=True))

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
    logger.info(f"add_text. ip: {request.client.host}. len: {len(text)}")
    if len(text) <= 0:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), "") + (no_change_btn,) * 5
    if args.moderate:
        flagged = violates_moderation(text)
        if flagged:
            state.skip_next = True
            return (state, state.to_gradio_chatbot(), moderation_msg) + (
                no_change_btn,) * 5

    text = text[:1536]  # Hard cut-off
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

def http_bot(state, temperature, max_new_tokens, request: gr.Request):
    start_tstamp = time.time()
    model_name = LLM_MODEL

    # TODO 这里的请求需要拼接现有知识库, 使得其根据现有知识库作答, 所以prompt需要继续优化
    if state.skip_next:
        # This generate call is skipped due to invalid inputs
        yield (state, state.to_gradio_chatbot()) + (no_change_btn,) * 5
        return

    if len(state.messages) == state.offset + 2:
        # First round of conversation
        
        template_name = "conv_one_shot"
        new_state = conv_templates[template_name].copy()
        new_state.conv_id = uuid.uuid4().hex
        new_state.append_message(new_state.roles[0], state.messages[-2][1])
        new_state.append_message(new_state.roles[1], None)
        state = new_state

    prompt = state.get_prompt()
    skip_echo_len = len(prompt.replace("</s>", " ")) + 1

    # Make requests
    payload = {
        "model": model_name,
        "prompt": prompt,
        "temperature": float(temperature),
        "max_new_tokens": int(max_new_tokens),
        "stop": state.sep if state.sep_style == SeparatorStyle.SINGLE else state.sep2,
    }
    logger.info(f"Requert: \n{payload}")

    state.messages[-1][-1] = "▌"
    yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5

    try:
        # Stream output
        response = requests.post(urljoin(vicuna_model_server, "generate_stream"),
            headers=headers, json=payload, stream=True, timeout=20)
        for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
            if chunk:
                data = json.loads(chunk.decode())
                if data["error_code"] == 0:
                    output = data["text"][skip_echo_len:].strip()
                    output = post_process_code(output)
                    state.messages[-1][-1] = output + "▌"
                    yield (state, state.to_gradio_chatbot()) + (disable_btn,) * 5
                else:
                    output = data["text"] + f" (error_code: {data['error_code']})"
                    state.messages[-1][-1] = output
                    yield (state, state.to_gradio_chatbot()) + (disable_btn, disable_btn, disable_btn, enable_btn, enable_btn)
                    return
                time.sleep(0.02)
    except requests.exceptions.RequestException as e:
        state.messages[-1][-1] = server_error_msg + f" (error_code: 4)"
        yield (state, state.to_gradio_chatbot()) + (disable_btn, disable_btn, disable_btn, enable_btn, enable_btn)
        return

    state.messages[-1][-1] = state.messages[-1][-1][:-1]
    yield (state, state.to_gradio_chatbot()) + (enable_btn,) * 5

    finish_tstamp = time.time()
    logger.info(f"{output}")

    with open(get_conv_log_filename(), "a") as fout:
        data = {
            "tstamp": round(finish_tstamp, 4),
            "type": "chat",
            "model": model_name,
            "start": round(start_tstamp, 4),
            "finish": round(start_tstamp, 4),
            "state": state.dict(),
            "ip": request.client.host,
        }
        fout.write(json.dumps(data) + "\n")

block_css = (
    code_highlight_css
    + """
pre {
    white-space: pre-wrap;       /* Since CSS 2.1 */
    white-space: -moz-pre-wrap;  /* Mozilla, since 1999 */
    white-space: -pre-wrap;      /* Opera 4-6 */
    white-space: -o-pre-wrap;    /* Opera 7 */
    word-wrap: break-word;       /* Internet Explorer 5.5+ */
}
#notice_markdown th {
    display: none;
}
    """
)


def build_single_model_ui():
   
    notice_markdown = """
    # DB-GPT
    
    [DB-GPT](https://github.com/csunny/DB-GPT) 是一个实验性的开源应用程序，它基于[FastChat](https://github.com/lm-sys/FastChat)，并使用vicuna-13b作为基础模型。此外，此程序结合了langchain和llama-index基于现有知识库进行In-Context Learning来对其进行数据库相关知识的增强。它可以进行SQL生成、SQL诊断、数据库知识问答等一系列的工作。 总的来说，它是一个用于数据库的复杂且创新的AI工具。如果您对如何在工作中使用或实施DB-GPT有任何具体问题，请联系我, 我会尽力提供帮助, 同时也欢迎大家参与到项目建设中, 做一些有趣的事情。 
    """
    learn_more_markdown = """ 
        ### Licence
        The service is a research preview intended for non-commercial use only. subject to the model [License](https://github.com/facebookresearch/llama/blob/main/MODEL_CARD.md) of LLaMA 
    """

    state = gr.State()
    gr.Markdown(notice_markdown, elem_id="notice_markdown")

    with gr.Accordion("参数", open=False, visible=False) as parameter_row:
        temperature = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=0.7,
            step=0.1,
            interactive=True,
            label="Temperature",
        )

        max_output_tokens = gr.Slider(
            minimum=0,
            maximum=1024,
            value=512,
            step=64,
            interactive=True,
            label="最大输出Token数",
        )

    with gr.Tabs():
        with gr.TabItem("知识问答", elem_id="QA"):
            pass

        with gr.TabItem("SQL生成与诊断", elem_id="SQL"):
            # TODO A selector to choose database
            pass 
    
    with gr.Blocks():
        chatbot = grChatbot(elem_id="chatbot", visible=False).style(height=550)
        with gr.Row():
            with gr.Column(scale=20):
                textbox = gr.Textbox(
                    show_label=False,
                    placeholder="Enter text and press ENTER",
                    visible=False,
                ).style(container=False)          
            with gr.Column(scale=2, min_width=50):
                send_btn = gr.Button(value="发送", visible=False) 

    with gr.Row(visible=False) as button_row:
        regenerate_btn = gr.Button(value="重新生成", interactive=False)
        clear_btn = gr.Button(value="清理", interactive=False)

    gr.Markdown(learn_more_markdown)

    btn_list = [regenerate_btn, clear_btn]
    regenerate_btn.click(regenerate, state, [state, chatbot, textbox] + btn_list).then(
        http_bot,
        [state, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )
    clear_btn.click(clear_history, None, [state, chatbot, textbox] + btn_list)
    
    textbox.submit(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, temperature, max_output_tokens],
        [state, chatbot] + btn_list,
    )

    send_btn.click(
        add_text, [state, textbox], [state, chatbot, textbox] + btn_list
    ).then(
        http_bot,
        [state, temperature, max_output_tokens],
        [state, chatbot] + btn_list
    )

    return state, chatbot, textbox, send_btn, button_row, parameter_row


def build_webdemo():
    with gr.Blocks(
        title="数据库智能助手",
        # theme=gr.themes.Base(),
        theme=gr.themes.Default(),
        css=block_css,
    ) as demo:
        url_params = gr.JSON(visible=False)
        (
            state,
            chatbot,
            textbox,
            send_btn,
            button_row,
            parameter_row,
        ) = build_single_model_ui()

        if args.model_list_mode == "once":
            demo.load(
                load_demo,
                [url_params],
                [
                    state,
                    chatbot,
                    textbox,
                    send_btn,
                    button_row,
                    parameter_row,
                ],
                _js=get_window_url_params,
            )
        else:
            raise ValueError(f"Unknown model list mode: {args.model_list_mode}")
    return demo

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument(
        "--model-list-mode", type=str, default="once", choices=["once", "reload"]
    )
    parser.add_argument("--share", default=False, action="store_true")
    parser.add_argument(
        "--moderate", action="store_true", help="Enable content moderation"
    )
    args = parser.parse_args()
    logger.info(f"args: {args}")

    logger.info(args)
    demo = build_webdemo()
    demo.queue(
        concurrency_count=args.concurrency_count, status_update_rate=10, api_open=False
    ).launch(
        server_name=args.host, server_port=args.port, share=args.share, max_threads=200,
    )