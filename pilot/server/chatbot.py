#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import requests
import json
import time
from urllib.parse import urljoin
import gradio as gr
from configs.model_config import *
vicuna_base_uri = "http://192.168.31.114:21002/"
vicuna_stream_path = "worker_generate_stream"
vicuna_status_path = "worker_get_status"

def generate(prompt):
    params = {
        "model": "vicuna-13b",
        "prompt": "给出一个查询用户的SQL",
        "temperature": 0.7,
        "max_new_tokens": 512,
        "stop": "###"
    }

    sts_response = requests.post(
        url=urljoin(vicuna_base_uri, vicuna_status_path)
    )
    print(sts_response.text)

    response = requests.post(
        url=urljoin(vicuna_base_uri, vicuna_stream_path), data=json.dumps(params)
    )

    skip_echo_len = len(params["prompt"]) + 1 - params["prompt"].count("</s>") * 3
    for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        if chunk:
            data = json.loads(chunk.decode())
            if data["error_code"] == 0:
                output = data["text"]
                yield(output) 
            
            time.sleep(0.02)

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

    