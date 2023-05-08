#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import requests
import json
import time
import uuid
from urllib.parse import urljoin
import gradio as gr
from pilot.configs.model_config import *
from pilot.conversation import conv_qa_prompt_template, conv_templates
from langchain.prompts import PromptTemplate

vicuna_stream_path = "generate_stream"

def generate(query):

    template_name = "conv_one_shot"
    state = conv_templates[template_name].copy()

    pt = PromptTemplate(
        template=conv_qa_prompt_template,
        input_variables=["context", "question"]
    )

    result = pt.format(context="This page covers how to use the Chroma ecosystem within LangChain. It is broken into two parts: installation and setup, and then references to specific Chroma wrappers.",
              question=query)

    print(result)

    state.append_message(state.roles[0], result)
    state.append_message(state.roles[1], None)

    prompt = state.get_prompt()
    params = {
        "model": "vicuna-13b",
        "prompt": prompt,
        "temperature": 0.7,
        "max_new_tokens": 1024,
        "stop": "###"
    }

    response = requests.post(
        url=urljoin(VICUNA_MODEL_SERVER, vicuna_stream_path), data=json.dumps(params)
    )

    skip_echo_len = len(params["prompt"]) + 1 - params["prompt"].count("</s>") * 3
    for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        if chunk:
            data = json.loads(chunk.decode())
            if data["error_code"] == 0:
                output = data["text"][skip_echo_len:].strip()
                state.messages[-1][-1] = output + "▌"
                yield(output) 
 
if __name__ == "__main__":
    print(LLM_MODEL)
    with gr.Blocks() as demo:
        gr.Markdown("数据库SQL生成助手")
        with gr.Tab("SQL生成"):
            text_input = gr.TextArea()
            text_output = gr.TextArea()
            text_button = gr.Button("提交")
        

        text_button.click(generate, inputs=text_input, outputs=text_output)

    demo.queue(concurrency_count=3).launch(server_name="0.0.0.0") 

    