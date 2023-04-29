#!/usr/bin/env python3 
# -*- coding:utf-8 -*-

import torch
import os

root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
model_path = os.path.join(root_path, "models")
vector_storepath = os.path.join(root_path, "vector_store")


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
llm_model_config = {
    "flan-t5-base": os.path.join(model_path, "flan-t5-base"),
    "vicuna-13b": os.path.join(model_path, "vicuna-13b")
}

LLM_MODEL = "vicuna-13b"


vicuna_model_server = "http://192.168.31.114:21000/"


# Load model config
isload_8bit = True
isdebug = False
