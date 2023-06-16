#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
import os
from typing import List
from functools import cache
from transformers import (
    AutoModel,
    AutoModelForCausalLM,
    AutoTokenizer,
    LlamaTokenizer,
    BitsAndBytesConfig,
)
from pilot.configs.model_config import DEVICE
from pilot.configs.config import Config

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="bfloat16",
    bnb_4bit_use_double_quant=False,
)
CFG = Config()


class BaseLLMAdaper:
    """The Base class for multi model, in our project.
    We will support those model, which performance resemble ChatGPT"""

    def match(self, model_path: str):
        return True

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, use_fast=False, trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            **from_pretrained_kwargs,
        )
        return model, tokenizer


llm_model_adapters: List[BaseLLMAdaper] = []


# Register llm models to adapters, by this we can use multi models.
def register_llm_model_adapters(cls):
    """Register a llm model adapter."""
    llm_model_adapters.append(cls())


@cache
def get_llm_model_adapter(model_path: str) -> BaseLLMAdaper:
    for adapter in llm_model_adapters:
        if adapter.match(model_path):
            return adapter

    raise ValueError(f"Invalid model adapter for {model_path}")


# TODO support cpu? for practice we support gpt4all or chatglm-6b-int4?


class VicunaLLMAdapater(BaseLLMAdaper):
    """Vicuna Adapter"""

    def match(self, model_path: str):
        return "vicuna" in model_path

    def loader(self, model_path: str, from_pretrained_kwagrs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, low_cpu_mem_usage=True, **from_pretrained_kwagrs
        )
        return model, tokenizer


class ChatGLMAdapater(BaseLLMAdaper):
    """LLM Adatpter for THUDM/chatglm-6b"""

    def match(self, model_path: str):
        return "chatglm" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        if DEVICE != "cuda":
            model = AutoModel.from_pretrained(
                model_path, trust_remote_code=True, **from_pretrained_kwargs
            ).float()
            return model, tokenizer
        else:
            model = (
                AutoModel.from_pretrained(
                    model_path, trust_remote_code=True, **from_pretrained_kwargs
                )
                .half()
                .cuda()
            )
            return model, tokenizer


class GuanacoAdapter(BaseLLMAdaper):
    """TODO Support guanaco"""

    def match(self, model_path: str):
        return "guanaco" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = LlamaTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, load_in_4bit=True, **from_pretrained_kwargs
        )
        return model, tokenizer


class FalconAdapater(BaseLLMAdaper):
    """falcon Adapter"""

    def match(self, model_path: str):
        return "falcon" in model_path

    def loader(self, model_path: str, from_pretrained_kwagrs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)

        if CFG.QLoRA:
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                load_in_4bit=True,  # quantize
                quantization_config=bnb_config,
                trust_remote_code=True,
                **from_pretrained_kwagrs,
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                **from_pretrained_kwagrs,
            )
        return model, tokenizer


class GorillaAdapter(BaseLLMAdaper):
    """TODO Support guanaco"""

    def match(self, model_path: str):
        return "gorilla" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, low_cpu_mem_usage=True, **from_pretrained_kwargs
        )
        return model, tokenizer


class CodeGenAdapter(BaseLLMAdaper):
    pass


class StarCoderAdapter(BaseLLMAdaper):
    pass


class T5CodeAdapter(BaseLLMAdaper):
    pass


class KoalaLLMAdapter(BaseLLMAdaper):
    """Koala LLM Adapter which Based LLaMA"""

    def match(self, model_path: str):
        return "koala" in model_path


class RWKV4LLMAdapter(BaseLLMAdaper):
    """LLM Adapter for RwKv4"""

    def match(self, model_path: str):
        return "RWKV-4" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        # TODO
        pass


class GPT4AllAdapter(BaseLLMAdaper):
    """
    A light version for someone who want practise LLM use laptop.
    All model names see: https://gpt4all.io/models/models.json
    """

    def match(self, model_path: str):
        return "gpt4all" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        import gpt4all

        if model_path is None and from_pretrained_kwargs.get("model_name") is None:
            model = gpt4all.GPT4All("ggml-gpt4all-j-v1.3-groovy")
        else:
            path, file = os.path.split(model_path)
            model = gpt4all.GPT4All(model_path=path, model_name=file)
        return model, None


class ProxyllmAdapter(BaseLLMAdaper):
    """The model adapter for local proxy"""

    def match(self, model_path: str):
        return "proxyllm" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        return "proxyllm", None


register_llm_model_adapters(VicunaLLMAdapater)
register_llm_model_adapters(ChatGLMAdapater)
register_llm_model_adapters(GuanacoAdapter)
register_llm_model_adapters(FalconAdapater)
register_llm_model_adapters(GorillaAdapter)
register_llm_model_adapters(GPT4AllAdapter)
# TODO Default support vicuna, other model need to tests and Evaluate

# just for test_py, remove this later
register_llm_model_adapters(ProxyllmAdapter)
register_llm_model_adapters(BaseLLMAdaper)
