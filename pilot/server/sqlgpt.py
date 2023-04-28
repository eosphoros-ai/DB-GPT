#!/usr/bin/env python3
#-*- coding: utf-8 -*-


import json
import torch
import gradio as gr
from fastchat.serve.inference import generate_stream, compress_module

from transformers import AutoTokenizer, AutoModelForCausalLM
device = "cuda" if torch.cuda.is_available() else "cpu"
BASE_MODE = "/home/magic/workspace/github/DB-GPT/models/vicuna-13b"

tokenizer = AutoTokenizer.from_pretrained(BASE_MODE, use_fast=False)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODE, 
    low_cpu_mem_usage=True, 
    torch_dtype=torch.float16,
    device_map="auto",
)

def generate(prompt):    
    # compress_module(model, device) 
    # model.to(device)
    print(model, tokenizer)
    params = {
        "model": "vicuna-13b",
        "prompt": "这是一个用户与助手之间的对话, 助手精通数据库领域的知识, 并能够对数据库领域知识做出非常专业的回答。以下是用户的问题:" + prompt,
        "temperature": 0.7,
        "max_new_tokens": 512,
        "stop": "###"
    }
    for output in generate_stream(
        model, tokenizer, params, device, context_len=2048, stream_interval=2):
        ret = {
            "text": output,
            "error_code": 0
        }
        
        yield json.dumps(ret).decode() + b"\0"

if __name__ == "__main__":
    with gr.Blocks() as demo:
        gr.Markdown("数据库SQL生成助手")
        with gr.Tab("SQL生成"):
            text_input = gr.TextArea()
            text_output = gr.TextArea()
            text_button = gr.Button("提交")
        

        text_button.click(generate, inputs=text_input, outputs=text_output)

    demo.queue(concurrency_count=3).launch(host="0.0.0.0") 



