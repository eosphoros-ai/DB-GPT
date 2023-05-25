#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os

import nltk
import torch

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(ROOT_PATH, "models")
PILOT_PATH = os.path.join(ROOT_PATH, "pilot")
VECTORE_PATH = os.path.join(PILOT_PATH, "vector_store")
LOGDIR = os.path.join(ROOT_PATH, "logs")
DATASETS_DIR = os.path.join(PILOT_PATH, "datasets")
DATA_DIR = os.path.join(PILOT_PATH, "data")

nltk.data.path = [os.path.join(PILOT_PATH, "nltk_data")] + nltk.data.path

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)
LLM_MODEL_CONFIG = {
    "flan-t5-base": os.path.join(MODEL_PATH, "flan-t5-base"),
    "vicuna-13b": os.path.join(MODEL_PATH, "vicuna-13b"),
    "vicuna-7b": os.path.join(MODEL_PATH, "vicuna-7b"),
    "text2vec": os.path.join(MODEL_PATH, "text2vec-large-chinese"),
    "sentence-transforms": os.path.join(MODEL_PATH, "all-MiniLM-L6-v2"),
    "codegen2-1b": os.path.join(MODEL_PATH, "codegen2-1B"),
    "codet5p-2b": os.path.join(MODEL_PATH, "codet5p-2b"),
    "chatglm-6b-int4": os.path.join(MODEL_PATH, "chatglm-6b-int4"),
    "chatglm-6b": os.path.join(MODEL_PATH, "chatglm-6b"),
    "text2vec-base": os.path.join(MODEL_PATH, "text2vec-base-chinese"),
    "sentence-transforms": os.path.join(MODEL_PATH, "all-MiniLM-L6-v2"),
}

# Load model config
ISLOAD_8BIT = True
ISDEBUG = False


VECTOR_SEARCH_TOP_K = 10
VS_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vs_store")
KNOWLEDGE_UPLOAD_ROOT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data"
)
KNOWLEDGE_CHUNK_SPLIT_SIZE = 100
