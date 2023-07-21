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


def auto_configure_device_map(num_gpus):
    """handling multi gpu calls"""
    # transformer.word_embeddings occupying 1 floors
    # transformer.final_layernorm and lm_head occupying 1 floors
    # transformer.layers occupying 28 floors
    # Allocate a total of 30 layers to number On gpus cards
    num_trans_layers = 28
    per_gpu_layers = 30 / num_gpus
    # Bugfix: call torch.embedding in Linux and the incoming weight and input are not on the same device, resulting in a RuntimeError
    # Under Windows, model. device will be set to transformer. word_ Embeddings. device
    # Under Linux, model. device will be set to lm_ Head.device
    # When calling chat or stream_ During chat, input_ IDS will be placed on model. device
    # If transformer. word_ If embeddings. device and model. device are different, it will cause a RuntimeError
    # Therefore, here we will transform. word_ Embeddings, transformer. final_ Layernorm, lm_ Put all the heads on the first card
    device_map = {
        "transformer.embedding.word_embeddings": 0,
        "transformer.encoder.final_layernorm": 0,
        "transformer.output_layer": 0,
        "transformer.rotary_pos_emb": 0,
        "lm_head": 0,
    }

    used = 2
    gpu_target = 0
    for i in range(num_trans_layers):
        if used >= per_gpu_layers:
            gpu_target += 1
            used = 0
        assert gpu_target < num_gpus
        device_map[f"transformer.encoder.layers.{i}"] = gpu_target
        used += 1

    return device_map


class ChatGLMAdapater(BaseLLMAdaper):
    """LLM Adatpter for THUDM/chatglm-6b"""

    def match(self, model_path: str):
        return "chatglm" in model_path

    def loader(
        self,
        model_path: str,
        from_pretrained_kwargs: dict,
        device_map=None,
        num_gpus=CFG.NUM_GPUS,
    ):
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
                ).half()
                # .cuda()
            )
            from accelerate import dispatch_model

            # model = AutoModel.from_pretrained(model_path, trust_remote_code=True,
            #                                   **from_pretrained_kwargs).half()
            #
            if device_map is None:
                device_map = auto_configure_device_map(num_gpus)

            model = dispatch_model(model, device_map=device_map)

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


class Llama2Adapter(BaseLLMAdaper):
    """The model adapter for llama-2"""

    def match(self, model_path: str):
        return "llama-2" in model_path.lower()

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        model, tokenizer = super().loader(model_path, from_pretrained_kwargs)
        model.config.eos_token_id = tokenizer.eos_token_id
        model.config.pad_token_id = tokenizer.pad_token_id
        return model, tokenizer


register_llm_model_adapters(VicunaLLMAdapater)
register_llm_model_adapters(ChatGLMAdapater)
register_llm_model_adapters(GuanacoAdapter)
register_llm_model_adapters(FalconAdapater)
register_llm_model_adapters(GorillaAdapter)
register_llm_model_adapters(GPT4AllAdapter)
register_llm_model_adapters(Llama2Adapter)
# TODO Default support vicuna, other model need to tests and Evaluate

# just for test_py, remove this later
register_llm_model_adapters(ProxyllmAdapter)
register_llm_model_adapters(BaseLLMAdaper)
