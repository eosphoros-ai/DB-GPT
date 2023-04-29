#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
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
        }

    def loader(self, load_8bit=False, debug=False):
       
        tokenizer = AutoTokenizer.from_pretrained(self.model_path, use_fast=False)
        model = AutoModelForCausalLM.from_pretrained(self.model_path, low_cpu_mem_usage=True, **self.kwargs)

        if debug:
            print(model)

        # if self.device == "cuda":
        #     model.to(self.device)

        return model, tokenizer


