#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    AutoModel
)

from fastchat.serve.compression import compress_module

class ModelLoader:
    """Model loader is a class for model load
    
      Args: model_path
     
    """

    kwargs = {}

    def __init__(self, 
                 model_path) -> None:
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_path = model_path 
        self.kwargs = {
            "torch_dtype": torch.float16,
            "device_map": "auto",
        }

    def loader(self, num_gpus, load_8bit=False, debug=False):
        if self.device == "cpu":
            kwargs = {}
        elif self.device == "cuda":
            kwargs = {"torch_dtype": torch.float16}
            if num_gpus == "auto":
                kwargs["device_map"] = "auto"
            else:
                num_gpus = int(num_gpus)
                if num_gpus != 1:
                    kwargs.update({
                        "device_map": "auto",
                        "max_memory": {i: "13GiB" for i in range(num_gpus)},
                    })
        else:
            raise ValueError(f"Invalid device: {self.device}")

        if "chatglm" in self.model_path:
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            model = AutoModel.from_pretrained(self.model_path, trust_remote_code=True).half().cuda()
        else:
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, use_fast=False)
            model = AutoModelForCausalLM.from_pretrained(self.model_path,
                low_cpu_mem_usage=True, **kwargs)

        if load_8bit:
            compress_module(model, self.device)

        if (self.device == "cuda" and num_gpus == 1):
            model.to(self.device)

        if debug:
            print(model)

        return model, tokenizer
 
