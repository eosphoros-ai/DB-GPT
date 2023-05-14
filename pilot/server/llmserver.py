#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uvicorn
import asyncio
import json
from typing import Optional, List
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pilot.model.inference import generate_stream
from pydantic import BaseModel
from pilot.model.inference import generate_output, get_embeddings

from pilot.model.loader import ModelLoader
from pilot.configs.model_config import *

model_path = LLM_MODEL_CONFIG[LLM_MODEL] 


global_counter = 0
model_semaphore = None

ml = ModelLoader(model_path=model_path)
model, tokenizer = ml.loader(num_gpus=1, load_8bit=ISLOAD_8BIT, debug=ISDEBUG)
#model, tokenizer = load_model(model_path=model_path, device=DEVICE, num_gpus=1, load_8bit=True, debug=False)

class ModelWorker:
    def __init__(self):
        pass

    # TODO 

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


def generate_stream_gate(params):
    try:
        for output in generate_stream(
            model, 
            tokenizer,
            params,
            DEVICE,
            MAX_POSITION_EMBEDDINGS,
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


@app.post("/generate_stream")
async def api_generate_stream(request: Request):
    global model_semaphore, global_counter
    global_counter += 1
    params = await request.json()
    print(model, tokenizer, params, DEVICE) 

    if model_semaphore is None:
        model_semaphore = asyncio.Semaphore(LIMIT_MODEL_CONCURRENCY)
    await model_semaphore.acquire() 

    generator = generate_stream_gate(params)
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
    output = generate_stream_gate(params)
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
    output = get_embeddings(model, tokenizer, params["prompt"])
    return {"response": [float(x) for x in output]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", log_level="info") 