#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

global_counter = 0
model_semaphore = None

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG
from pilot.model.worker.manager import run_worker_manager

CFG = Config()

model_path = LLM_MODEL_CONFIG[CFG.LLM_MODEL]
# worker = ModelWorker(model_path=model_path, model_name=CFG.LLM_MODEL, device=DEVICE)

# @app.post("/embedding")
# def embeddings(prompt_request: EmbeddingRequest):
#     params = {"prompt": prompt_request.prompt}
#     print("Received prompt: ", params["prompt"])
#     output = worker.get_embeddings(params["prompt"])
#     return {"response": [float(x) for x in output]}


if __name__ == "__main__":
    run_worker_manager(
        model_name=CFG.LLM_MODEL,
        model_path=model_path,
        standalone=True,
        port=CFG.MODEL_PORT,
    )
