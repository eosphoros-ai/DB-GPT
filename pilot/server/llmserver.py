#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import sys

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import StreamingResponse

# from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

global_counter = 0
model_semaphore = None

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.configs.config import Config
from pilot.configs.model_config import *
from pilot.model.llm_out.vicuna_base_llm import get_embeddings
from pilot.model.loader import ModelLoader
from pilot.server.chat_adapter import get_llm_chat_adapter

CFG = Config()


class ModelWorker:
    def __init__(self, model_path, model_name, device, num_gpus=1):
        if model_path.endswith("/"):
            model_path = model_path[:-1]
        self.model_name = model_name or model_path.split("/")[-1]
        self.device = device
        print(f"Loading {model_name} LLM ModelServer in {device}! Please Wait......")
        self.ml = ModelLoader(model_path=model_path)
        self.model, self.tokenizer = self.ml.loader(
            num_gpus, load_8bit=ISLOAD_8BIT, debug=ISDEBUG
        )

        if not isinstance(self.model, str):
            if hasattr(self.model, "config") and hasattr(
                self.model.config, "max_sequence_length"
            ):
                self.context_len = self.model.config.max_sequence_length
            elif hasattr(self.model, "config") and hasattr(
                self.model.config, "max_position_embeddings"
            ):
                self.context_len = self.model.config.max_position_embeddings

        else:
            self.context_len = 2048

        self.llm_chat_adapter = get_llm_chat_adapter(model_path)
        self.generate_stream_func = self.llm_chat_adapter.get_generate_stream_func()

    def start_check(self):
        print("LLM Model Loading Success！")

    def get_queue_length(self):
        if (
            model_semaphore is None
            or model_semaphore._value is None
            or model_semaphore._waiters is None
        ):
            return 0
        else:
            (
                CFG.LIMIT_MODEL_CONCURRENCY
                - model_semaphore._value
                + len(model_semaphore._waiters)
            )

    def generate_stream_gate(self, params):
        try:
            for output in self.generate_stream_func(
                self.model, self.tokenizer, params, DEVICE, CFG.MAX_POSITION_EMBEDDINGS
            ):
                # Please do not open the output in production!
                # The gpt4all thread shares stdout with the parent process,
                # and opening it may affect the frontend output.
                print("output: ", output)
                ret = {
                    "text": output,
                    "error_code": 0,
                }
                yield json.dumps(ret).encode() + b"\0"

        except torch.cuda.CudaError:
            ret = {"text": "**GPU OutOfMemory, Please Refresh.**", "error_code": 0}
            yield json.dumps(ret).encode() + b"\0"
        except Exception as e:
            ret = {
                "text": f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                "error_code": 0,
            }
            yield json.dumps(ret).encode() + b"\0"

    def get_embeddings(self, prompt):
        return get_embeddings(self.model, self.tokenizer, prompt)


model_path = LLM_MODEL_CONFIG[CFG.LLM_MODEL]
worker = ModelWorker(
    model_path=model_path, model_name=CFG.LLM_MODEL, device=DEVICE, num_gpus=1
)

app = FastAPI()
# from pilot.openapi.knowledge.knowledge_controller import router
#
# app.include_router(router)
#
# origins = [
#     "http://localhost",
#     "http://localhost:8000",
#     "http://localhost:3000",
# ]
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


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
def generate(prompt_request: PromptRequest) -> str:
    params = {
        "prompt": prompt_request.prompt,
        "temperature": prompt_request.temperature,
        "max_new_tokens": prompt_request.max_new_tokens,
        "stop": prompt_request.stop,
    }

    rsp_str = ""
    output = worker.generate_stream_gate(params)
    for rsp in output:
        # rsp = rsp.decode("utf-8")
        rsp = rsp.replace(b"\0", b"")
        rsp_str = rsp.decode()

    return rsp_str


@app.post("/embedding")
def embeddings(prompt_request: EmbeddingRequest):
    params = {"prompt": prompt_request.prompt}
    print("Received prompt: ", params["prompt"])
    output = worker.get_embeddings(params["prompt"])
    return {"response": [float(x) for x in output]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=CFG.MODEL_PORT, log_level="info")
