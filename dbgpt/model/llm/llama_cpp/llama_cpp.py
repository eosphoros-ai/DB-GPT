"""
Fork from text-generation-webui https://github.com/oobabooga/text-generation-webui/blob/main/modules/llamacpp_model.py
"""
import re
from typing import Dict
import logging
import torch
import llama_cpp

from dbgpt.model.parameter import LlamaCppModelParameters

logger = logging.getLogger(__name__)

if torch.cuda.is_available() and not torch.version.hip:
    try:
        import llama_cpp_cuda
    except:
        llama_cpp_cuda = None
else:
    llama_cpp_cuda = None


def llama_cpp_lib(prefer_cpu: bool = False):
    if prefer_cpu or llama_cpp_cuda is None:
        logger.info(f"Llama.cpp use cpu")
        return llama_cpp
    else:
        return llama_cpp_cuda


def ban_eos_logits_processor(eos_token, input_ids, logits):
    logits[eos_token] = -float("inf")
    return logits


def get_params(model_path: str, model_params: LlamaCppModelParameters) -> Dict:
    return {
        "model_path": model_path,
        "n_ctx": model_params.max_context_size,
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
    def from_pretrained(self, model_path, model_params: LlamaCppModelParameters):
        Llama = llama_cpp_lib(prefer_cpu=model_params.prefer_cpu).Llama
        LlamaCache = llama_cpp_lib(prefer_cpu=model_params.prefer_cpu).LlamaCache

        result = self()
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

        # This is ugly, but the model and the tokenizer are the same object in this library.
        return result, result

    def encode(self, string):
        if type(string) is str:
            string = string.encode()

        return self.model.tokenize(string)

    def decode(self, tokens):
        return self.model.detokenize(tokens)

    def generate_streaming(self, params, context_len: int):
        # LogitsProcessorList = llama_cpp_lib().LogitsProcessorList

        # Read parameters
        prompt = params["prompt"]
        if self.verbose:
            print(f"Prompt of model: \n{prompt}")

        temperature = float(params.get("temperature", 1.0))
        repetition_penalty = float(params.get("repetition_penalty", 1.1))
        top_p = float(params.get("top_p", 1.0))
        top_k = int(params.get("top_k", -1))  # -1 means disable
        max_new_tokens = int(params.get("max_new_tokens", 2048))
        echo = bool(params.get("echo", True))

        max_src_len = context_len - max_new_tokens
        # Handle truncation
        prompt = self.encode(prompt)
        prompt = prompt[-max_src_len:]
        prompt = self.decode(prompt).decode("utf-8")

        # TODO Compared with the original llama model, the Chinese effect of llama.cpp is very general, and it needs to be debugged
        completion_chunks = self.model.create_completion(
            prompt=prompt,
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repetition_penalty,
            # tfs_z=params['tfs'],
            # mirostat_mode=int(params['mirostat_mode']),
            # mirostat_tau=params['mirostat_tau'],
            # mirostat_eta=params['mirostat_eta'],
            stream=True,
            echo=echo,
            logits_processor=None,
        )

        output = ""
        for completion_chunk in completion_chunks:
            text = completion_chunk["choices"][0]["text"]
            output += text
            # print(output)
            yield output
