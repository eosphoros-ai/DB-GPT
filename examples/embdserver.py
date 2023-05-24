#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import os
import sys
from urllib.parse import urljoin

import gradio as gr
import requests

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_PATH)


from langchain.prompts import PromptTemplate

from pilot.configs.config import Config
from pilot.conversation import conv_qa_prompt_template, conv_templates

llmstream_stream_path = "generate_stream"

CFG = Config()


def generate(query):
    template_name = "conv_one_shot"
    state = conv_templates[template_name].copy()

    # pt = PromptTemplate(
    #     template=conv_qa_prompt_template,
    #     input_variables=["context", "question"]
    # )

    # result = pt.format(context="This page covers how to use the Chroma ecosystem within LangChain. It is broken into two parts: installation and setup, and then references to specific Chroma wrappers.",
    #           question=query)

    # print(result)

    state.append_message(state.roles[0], query)
    state.append_message(state.roles[1], None)

    prompt = state.get_prompt()
    params = {
        "model": "chatglm-6b",
        "prompt": prompt,
        "temperature": 1.0,
        "max_new_tokens": 1024,
        "stop": "###",
    }

    response = requests.post(
        url=urljoin(CFG.MODEL_SERVER, llmstream_stream_path), data=json.dumps(params)
    )

    skip_echo_len = len(params["prompt"]) + 1 - params["prompt"].count("</s>") * 3

    for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        if chunk:
            data = json.loads(chunk.decode())
            if data["error_code"] == 0:
                if "vicuna" in CFG.LLM_MODEL:
                    output = data["text"][skip_echo_len:].strip()
                else:
                    output = data["text"].strip()

                state.messages[-1][-1] = output + "▌"
                yield (output)


if __name__ == "__main__":
    print(CFG.LLM_MODEL)
    with gr.Blocks() as demo:
        gr.Markdown("数据库SQL生成助手")
        with gr.Tab("SQL生成"):
            text_input = gr.TextArea()
            text_output = gr.TextArea()
            text_button = gr.Button("提交")

        text_button.click(generate, inputs=text_input, outputs=text_output)

    demo.queue(concurrency_count=3).launch(server_name="0.0.0.0")
