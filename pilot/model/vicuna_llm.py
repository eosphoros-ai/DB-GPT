#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import requests
from typing import Any, Mapping, Optional, List
from transformers import pipeline
from langchain.llms.base import LLM
from configs.model_config import *

class VicunaLLM(LLM):

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        url = vicuna_model_server
        params = {
            "model": "vicuna-13b",
            "prompt": prompt,
            "temperature": 0.7,
            "max_new_tokens": 512,
            "stop": "###"
        }
        pass

    @property
    def _llm_type(self) -> str:
        return "custome"

    def _identifying_params(self) -> Mapping[str, Any]:
        return {}
    