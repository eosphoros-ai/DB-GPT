#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import torch
from fastchat.serve.inference import generate_stream, compress_module

BASE_MODE = "/home/magic/workspace/github/DB-GPT/models/vicuna-13b"
from transformers import AutoTokenizer, AutoModelForCausalLM

if __name__ == "__main__":

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODE, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODE, 
        low_cpu_mem_usage=True, 
        torch_dtype=torch.float16,
        device_map="auto",
        )

    print(device)
    #compress_module(model, device) 
    print(model, tokenizer)