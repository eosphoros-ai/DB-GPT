#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG, EMBEDDING_MODEL_CONFIG
from pilot.model.cluster import run_worker_manager

CFG = Config()

model_path = LLM_MODEL_CONFIG[CFG.LLM_MODEL]

if __name__ == "__main__":
    run_worker_manager(
        model_name=CFG.LLM_MODEL,
        model_path=model_path,
        standalone=True,
        port=CFG.MODEL_PORT,
        embedding_model_name=CFG.EMBEDDING_MODEL,
        embedding_model_path=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
    )
