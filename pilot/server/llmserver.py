#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uvicorn
import asyncio
import json
import sys
from typing import Optional, List
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

global_counter = 0
model_semaphore = None

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.model.inference import generate_stream
from pilot.model.inference import generate_output, get_embeddings

from pilot.model.loader import ModelLoader
from pilot.configs.model_config import *
from pilot.configs.config import  Config
from pilot.server.chat_adapter import get_llm_chat_adapter


CFG = Config()

class ModelWorker:

    def __init__(self, model_path, model_name, device, num_gpus=1):
        
        if model_path.endswith("/"):
            model_path = model_path[:-1]
        self.model_name = model_name or model_path.split("/")[-1]
        self.device = device

        self.ml = ModelLoader(model_path=model_path)
        self.model, self.tokenizer = self.ml.loader(num_gpus, load_8bit=ISLOAD_8BIT, debug=ISDEBUG)

        if hasattr(self.model.config, "max_sequence_length"):
            self.context_len = self.model.config.max_sequence_length
        elif hasattr(self.model.config, "max_position_embeddings"):
            self.context_len = self.model.config.max_position_embeddings

        else:
            self.context_len = 2048
        
        self.llm_chat_adapter = get_llm_chat_adapter(model_path)
        self.generate_stream_func = self.llm_chat_adapter.get_generate_stream_func() 

    def get_queue_length(self):
        if model_semaphore is None or model_semaphore._value is None or model_semaphore._waiters is None:
            return 0
        else:
            CFG.LIMIT_MODEL_CONCURRENCY - model_semaphore._value + len(model_semaphore._waiters)

    def generate_stream_gate(self, params):
        try:
            for output in self.generate_stream_func(
                self.model, 
                self.tokenizer, 
                params, 
                DEVICE, 
                CFG.MAX_POSITION_EMBEDDINGS
            ):
                print("output: ", output)
                ret = {
                    "text": output,
                    "error_code": 0,
                }
                yield json.dumps(ret).encode() + b"\0"

        except torch.cuda.CudaError:
            ret = {
                "text": "**GPU OutOfMemory, Please Refresh.**",
                "error_code": 0
            }
            yield json.dumps(ret).encode() + b"\0"

    def get_embeddings(self, prompt):
        return get_embeddings(self.model, self.tokenizer, prompt)

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    temperature: float
    max_new_tokens: int
    model: str
    stop: str = None

class StreamRequest(BaseModel):
    model: str
    prompt: str
    temperature: float
    max_new_tokens: int
    stop: str

class EmbeddingRequest(BaseModel):
    prompt: str

def release_model_semaphore():
    model_semaphore.release()


@app.post("/generate_stream")
async def api_generate_stream(request: Request):
    global model_semaphore, global_counter
    global_counter += 1
    params = await request.json()

    if model_semaphore is None:
        model_semaphore = asyncio.Semaphore(CFG.LIMIT_MODEL_CONCURRENCY)
    await model_semaphore.acquire() 

    generator = worker.generate_stream_gate(params)
    background_tasks = BackgroundTasks()
    background_tasks.add_task(release_model_semaphore)
    return StreamingResponse(generator, background=background_tasks)

@app.post("/generate")
def generate(prompt_request: PromptRequest):
    params = {
        "prompt": prompt_request.prompt,
        "temperature": prompt_request.temperature,
        "max_new_tokens": prompt_request.max_new_tokens,
        "stop": prompt_request.stop
    }

    response = [] 
    rsp_str = ""
    output = worker.generate_stream_gate(params)
    for rsp in output:
        # rsp = rsp.decode("utf-8")
        rsp_str = str(rsp, "utf-8")
        print("[TEST: output]:", rsp_str)
        response.append(rsp_str)

    return {"response": rsp_str}
    

@app.post("/embedding")
def embeddings(prompt_request: EmbeddingRequest):
    params = {"prompt": prompt_request.prompt}
    print("Received prompt: ", params["prompt"])
    output = worker.get_embeddings(params["prompt"])
    return {"response": [float(x) for x in output]}


if __name__ == "__main__":

    model_path = LLM_MODEL_CONFIG[CFG.LLM_MODEL]
    print(model_path, DEVICE)
    
    
    worker = ModelWorker(
        model_path=model_path, 
        model_name=CFG.LLM_MODEL, 
        device=DEVICE, 
        num_gpus=1
    )

    uvicorn.run(app, host="0.0.0.0", port=CFG.MODEL_PORT, log_level="info")