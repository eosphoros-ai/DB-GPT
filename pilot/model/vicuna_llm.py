#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from transformers import pipeline
from langchain.llms.base import LLM
from configs.model_config import *

class VicunaLLM(LLM):
    model_name = llm_model_config[LLM_MODEL]
