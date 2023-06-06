#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from functools import cache
from typing import List

from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer, LlamaTokenizer

from pilot.configs.model_config import DEVICE


class BaseLLMAdaper:
    """The Base class for multi model, in our project.
    We will support those model, which performance resemble ChatGPT"""

    def match(self, model_path: str):
        return True

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, low_cpu_mem_usage=True, **from_pretrained_kwargs
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


# TODO support cpu? for practise we support gpt4all or chatglm-6b-int4?


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
            model_path, load_in_4bit=True, device_map={"": 0}, **from_pretrained_kwargs
        )
        return model, tokenizer


class GuanacoAdapter(BaseLLMAdaper):
    """TODO Support guanaco"""

    def match(self, model_path: str):
        return "guanaco" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = LlamaTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, load_in_4bit=True, device_map={"": 0}, **from_pretrained_kwargs
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
    """A light version for someone who want practise LLM use laptop."""

    def match(self, model_path: str):
        return "gpt4all" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        # TODO
        pass


class ProxyllmAdapter(BaseLLMAdaper):

    """The model adapter for local proxy"""

    def match(self, model_path: str):
        return "proxyllm" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        return "proxyllm", None


register_llm_model_adapters(VicunaLLMAdapater)
register_llm_model_adapters(ChatGLMAdapater)
register_llm_model_adapters(GuanacoAdapter)
# TODO Default support vicuna, other model need to tests and Evaluate

# just for test, remove this later
register_llm_model_adapters(ProxyllmAdapter)
register_llm_model_adapters(BaseLLMAdaper)
