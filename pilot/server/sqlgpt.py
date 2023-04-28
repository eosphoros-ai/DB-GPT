#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import json
import torch
from fastchat.serve.inference import generate_stream, compress_module


from transformers import AutoTokenizer, AutoModelForCausalLM
device = "cuda" if torch.cuda.is_available() else "cpu"
BASE_MODE = "/home/magic/workspace/github/DB-GPT/models/vicuna-13b"

def generate(prompt):    
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODE, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODE, 
        low_cpu_mem_usage=True, 
        torch_dtype=torch.float16,
        device_map="auto",
    )
    # compress_module(model, device) 
    # model.to(device)
    print(model, tokenizer)

    params = {
        "model": "vicuna-13b",
        "prompt": prompt,
        "temperature": 0.7,
        "max_new_tokens": 512,
        "stop": "###"
    }
    output = generate_stream(
        model, tokenizer, params, device, context_len=2048, stream_interval=2)

    yield output

if __name__ == "__main__":
    pass





