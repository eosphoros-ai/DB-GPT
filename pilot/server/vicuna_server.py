#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, List
from fastapi import FastAPI
from pydantic import BaseModel
from pilot.model.inference import generate_output, get_embeddings
from pilot.model.loader import ModerLoader
from pilot.configs.model_config import *

model_path = llm_model_config[LLM_MODEL] 
ml = ModerLoader(model_path=model_path)
model, tokenizer = ml.loader(load_8bit=isload_8bit, debug=isdebug)

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    temperature: float
    max_new_tokens: int
    stop: Optional[List[str]] = None


class EmbeddingRequest(BaseModel):
    prompt: str


@app.post("/generate")
def generate(prompt_request: PromptRequest):
    params = {
        "prompt": prompt_request.prompt,
        "temperature": prompt_request.temperature,
        "max_new_tokens": prompt_request.max_new_tokens,
        "stop": prompt_request.stop
    }

    print("Receive prompt: ", params["prompt"])
    output = generate_output(model, tokenizer, params, DEVICE)
    print("Output: ", output)
    return {"response": output}


@app.post("/embedding")
def embeddings(prompt_request: EmbeddingRequest):
    params = {"prompt": prompt_request.prompt}
    print("Received prompt: ", params["prompt"])
    output = get_embeddings(model, tokenizer, params["prompt"])
    return {"response": [float(x) for x in output]}