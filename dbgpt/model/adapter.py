"""
This code file will be deprecated in the future. 
We have integrated fastchat. For details, see: dbgpt/model/model_adapter.py
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
from pathlib import Path
from typing import List, Tuple
from functools import cache
from transformers import (
    AutoModel,
    AutoModelForCausalLM,
    AutoTokenizer,
    LlamaTokenizer,
)
from dbgpt.model.base import ModelType

from dbgpt.model.parameter import (
    ModelParameters,
    LlamaCppModelParameters,
    ProxyModelParameters,
)
from dbgpt.configs.model_config import get_device
from dbgpt._private.config import Config

logger = logging.getLogger(__name__)

CFG = Config()


class BaseLLMAdaper:
    """The Base class for multi model, in our project.
    We will support those model, which performance resemble ChatGPT"""

    def use_fast_tokenizer(self) -> bool:
        return False

    def model_type(self) -> str:
        return ModelType.HF

    def model_param_class(self, model_type: str = None) -> ModelParameters:
        model_type = model_type if model_type else self.model_type()
        if model_type == ModelType.LLAMA_CPP:
            return LlamaCppModelParameters
        elif model_type == ModelType.PROXY:
            return ProxyModelParameters
        return ModelParameters

    def match(self, model_path: str):
        return False

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
def get_llm_model_adapter(model_name: str, model_path: str) -> BaseLLMAdaper:
    # Prefer using model name matching
    for adapter in llm_model_adapters:
        if adapter.match(model_name):
            logger.info(
                f"Found llm model adapter with model name: {model_name}, {adapter}"
            )
            return adapter

    for adapter in llm_model_adapters:
        if model_path and adapter.match(model_path):
            logger.info(
                f"Found llm model adapter with model path: {model_path}, {adapter}"
            )
            return adapter

    raise ValueError(
        f"Invalid model adapter for model name {model_name} and model path {model_path}"
    )


def _parse_model_param_class(model_name: str, model_path: str) -> ModelParameters:
    try:
        llm_adapter = get_llm_model_adapter(model_name, model_path)
        return llm_adapter.model_param_class()
    except Exception as e:
        logger.warn(
            f"Parse model parameters with model name {model_name} and model {model_path} failed {str(e)}, return `ModelParameters`"
        )
        return ModelParameters


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

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        import torch

        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        if get_device() != "cuda":
            model = AutoModel.from_pretrained(
                model_path, trust_remote_code=True, **from_pretrained_kwargs
            ).float()
            return model, tokenizer
        else:
            device_map = None
            num_gpus = torch.cuda.device_count()
            model = (
                AutoModel.from_pretrained(
                    model_path, trust_remote_code=True, **from_pretrained_kwargs
                ).half()
                # .cuda()
            )
            from accelerate import dispatch_model

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
            from transformers import BitsAndBytesConfig

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype="bfloat16",
                bnb_4bit_use_double_quant=False,
            )
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


class StarCoderAdapter(BaseLLMAdaper):
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
        return "gptj-6b" in model_path

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

    def model_type(self) -> str:
        return ModelType.PROXY

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


class CodeLlamaAdapter(BaseLLMAdaper):
    """The model adapter for codellama"""

    def match(self, model_path: str):
        return "codellama" in model_path.lower()

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        model, tokenizer = super().loader(model_path, from_pretrained_kwargs)
        model.config.eos_token_id = tokenizer.eos_token_id
        model.config.pad_token_id = tokenizer.pad_token_id
        return model, tokenizer


class BaichuanAdapter(BaseLLMAdaper):
    """The model adapter for Baichuan models (e.g., baichuan-inc/Baichuan-13B-Chat)"""

    def match(self, model_path: str):
        return "baichuan" in model_path.lower()

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True, use_fast=False
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            **from_pretrained_kwargs,
        )
        return model, tokenizer


class WizardLMAdapter(BaseLLMAdaper):
    def match(self, model_path: str):
        return "wizardlm" in model_path.lower()


class LlamaCppAdapater(BaseLLMAdaper):
    @staticmethod
    def _parse_model_path(model_path: str) -> Tuple[bool, str]:
        path = Path(model_path)
        if not path.exists():
            # Just support local model
            return False, None
        if not path.is_file():
            model_paths = list(path.glob("*ggml*.gguf"))
            if not model_paths:
                return False, None
            model_path = str(model_paths[0])
            logger.warn(
                f"Model path {model_path} is not single file, use first *gglm*.gguf model file: {model_path}"
            )
        if not re.fullmatch(".*ggml.*\.gguf", model_path):
            return False, None
        return True, model_path

    def model_type(self) -> ModelType:
        return ModelType.LLAMA_CPP

    def match(self, model_path: str):
        """
        https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGML
        """
        if "llama-cpp" == model_path:
            return True
        is_match, _ = LlamaCppAdapater._parse_model_path(model_path)
        return is_match

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        # TODO not support yet
        _, model_path = LlamaCppAdapater._parse_model_path(model_path)
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True, use_fast=False
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            **from_pretrained_kwargs,
        )
        return model, tokenizer


class InternLMAdapter(BaseLLMAdaper):
    """The model adapter for internlm/internlm-chat-7b"""

    def match(self, model_path: str):
        return "internlm" in model_path.lower()

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        revision = from_pretrained_kwargs.get("revision", "main")
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            **from_pretrained_kwargs,
        )
        model = model.eval()
        if "8k" in model_path.lower():
            model.config.max_sequence_length = 8192
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, use_fast=False, trust_remote_code=True, revision=revision
        )
        return model, tokenizer


register_llm_model_adapters(VicunaLLMAdapater)
register_llm_model_adapters(ChatGLMAdapater)
register_llm_model_adapters(GuanacoAdapter)
register_llm_model_adapters(FalconAdapater)
register_llm_model_adapters(GorillaAdapter)
register_llm_model_adapters(GPT4AllAdapter)
register_llm_model_adapters(Llama2Adapter)
register_llm_model_adapters(CodeLlamaAdapter)
register_llm_model_adapters(BaichuanAdapter)
register_llm_model_adapters(WizardLMAdapter)
register_llm_model_adapters(LlamaCppAdapater)
register_llm_model_adapters(InternLMAdapter)
# TODO Default support vicuna, other model need to tests and Evaluate

# just for test_py, remove this later
register_llm_model_adapters(ProxyllmAdapter)
register_llm_model_adapters(BaseLLMAdaper)
