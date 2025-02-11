"""
Fork from text-generation-webui https://github.com/oobabooga/text-generation-webui/blob/main/modules/llamacpp_model.py
"""

import logging
import re
from typing import Dict

import llama_cpp
import torch

from dbgpt.core import ModelOutput
from dbgpt.model.parameter import LlamaCppModelParameters
from dbgpt.model.utils.llm_utils import parse_model_request

logger = logging.getLogger(__name__)

if torch.cuda.is_available() and not torch.version.hip:
    try:
        import llama_cpp_cuda
    except ImportError:
        llama_cpp_cuda = None
else:
    llama_cpp_cuda = None


def llama_cpp_lib(prefer_cpu: bool = False):
    if prefer_cpu or llama_cpp_cuda is None:
        logger.info("Llama.cpp use cpu")
        return llama_cpp
    else:
        return llama_cpp_cuda


def ban_eos_logits_processor(eos_token, input_ids, logits):
    logits[eos_token] = -float("inf")
    return logits


def get_params(model_path: str, model_params: LlamaCppModelParameters) -> Dict:
    return {
        "model_path": model_path,
        "n_ctx": model_params.context_length or 4096,
        "seed": model_params.seed,
        "n_threads": model_params.n_threads,
        "n_batch": model_params.n_batch,
        "use_mmap": True,
        "use_mlock": False,
        "low_vram": False,
        "n_gpu_layers": 0 if model_params.prefer_cpu else model_params.n_gpu_layers,
        "n_gqa": model_params.n_gqa,
        "logits_all": True,
        "rms_norm_eps": model_params.rms_norm_eps,
    }


class LlamaCppModel:
    def __init__(self):
        self.initialized = False
        self.model = None
        self.verbose = True

    def __del__(self):
        if self.model:
            self.model.__del__()

    @classmethod
    def from_pretrained(cls, model_path, model_params: LlamaCppModelParameters):
        Llama = llama_cpp_lib(prefer_cpu=model_params.prefer_cpu).Llama
        LlamaCache = llama_cpp_lib(prefer_cpu=model_params.prefer_cpu).LlamaCache

        result = cls()
        cache_capacity = 0
        cache_capacity_str = model_params.cache_capacity
        if cache_capacity_str is not None:
            if "GiB" in cache_capacity_str:
                cache_capacity = (
                    int(re.sub("[a-zA-Z]", "", cache_capacity_str)) * 1000 * 1000 * 1000
                )
            elif "MiB" in cache_capacity_str:
                cache_capacity = (
                    int(re.sub("[a-zA-Z]", "", cache_capacity_str)) * 1000 * 1000
                )
            else:
                cache_capacity = int(cache_capacity_str)

        params = get_params(model_path, model_params)
        logger.info("Cache capacity is " + str(cache_capacity) + " bytes")
        logger.info(f"Load LLama model with params: {params}")

        result.model = Llama(**params)
        result.verbose = model_params.verbose
        if cache_capacity > 0:
            result.model.set_cache(LlamaCache(capacity_bytes=cache_capacity))

        # This is ugly, but the model and the tokenizer are the same object in this
        # library.
        return result, result

    def encode(self, string):
        if type(string) is str:
            string = string.encode()

        return self.model.tokenize(string)

    def decode(self, tokens):
        return self.model.detokenize(tokens)

    def generate_streaming(self, params, context_len: int):
        request = parse_model_request(params, default_model=params.get("model"))
        messages = request.to_common_messages()
        repetition_penalty = float(params.get("repetition_penalty", 1.1))
        top_k = int(params.get("top_k", -1))  # -1 means disable
        # Handle truncation
        completion_chunks = self.model.create_chat_completion(
            messages=messages,
            max_tokens=request.max_new_tokens,
            temperature=request.temperature or 0.8,
            top_p=request.top_p or 0.95,
            top_k=top_k,
            repeat_penalty=repetition_penalty,
            stream=True,
            logits_processor=None,
        )

        text = ""
        for r in completion_chunks:
            if not r.get("choices"):
                continue
            if r["choices"][0]["delta"].get("content") is not None:
                content = r["choices"][0]["delta"]["content"]
                text += content
                yield ModelOutput(text=text, error_code=0)
