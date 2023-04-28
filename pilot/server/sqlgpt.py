#!/usr/bin/env python3
#-*- coding: utf-8 -*-

from pilot.model.loader import ModerLoader
from fastchat.serve.inference import generate_stream
from pilot.configs.model_config import *

if __name__ == "__main__":

    model_path = llm_model_config[LLM_MODEL]

    ml = ModerLoader(model_path)
    model, tokenizer = ml.loader(load_8bit=True) 
    print(model)
    print(tokenizer)