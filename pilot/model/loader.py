#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
import warnings
from pilot.singleton import Singleton

from pilot.model.compression import compress_module 
from pilot.model.adapter import get_llm_model_adapter


class ModelLoader(metaclass=Singleton):
    """Model loader is a class for model load
    
      Args: model_path

    TODO: multi model support. 
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

    # TODO multi gpu support
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
            # Todo Support mps for practise
            raise ValueError(f"Invalid device: {self.device}")

        
        llm_adapter = get_llm_model_adapter(self.model_path)
        model, tokenizer = llm_adapter.loader(self.model_path, kwargs)

        if load_8bit:
            if num_gpus != 1:
                warnings.warn(
                    "8-bit quantization is not supported for multi-gpu inference"
                )
            else:
                compress_module(model, self.device) 

        if (self.device == "cuda" and num_gpus == 1):
            model.to(self.device)

        if debug:
            print(model)

        return model, tokenizer
 
