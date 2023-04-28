#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
from pilot.utils import get_gpu_memory
from fastchat.serve.inference import compress_module
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
)

class ModerLoader:

    kwargs = {}

    def __init__(self, 
                 model_path) -> None:
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_path = model_path 
        self.kwargs = {
            "torch_dtype": torch.float16,
            "device_map": "auto",
            "max_memory": get_gpu_memory(),
        }

    def loader(self, load_8bit=False, debug=False):
       
        tokenizer = AutoTokenizer.from_pretrained(self.model_path, use_fast=False)
        model = AutoModelForCausalLM.from_pretrained(self.model_path, low_cpu_mem_usage=True, **self.kwargs)

        if load_8bit:
            compress_module(model, self.device)

        if debug:
            print(model)

        return model, tokenizer


