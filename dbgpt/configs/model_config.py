#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
from functools import cache

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(ROOT_PATH, "models")
PILOT_PATH = os.path.join(ROOT_PATH, "pilot")
LOGDIR = os.getenv("DBGPT_LOG_DIR", os.path.join(ROOT_PATH, "logs"))
STATIC_MESSAGE_IMG_PATH = os.path.join(PILOT_PATH, "message/img")

DATASETS_DIR = os.path.join(PILOT_PATH, "datasets")
DATA_DIR = os.path.join(PILOT_PATH, "data")
PLUGINS_DIR = os.path.join(ROOT_PATH, "plugins")
MODEL_DISK_CACHE_DIR = os.path.join(DATA_DIR, "model_cache")
FILE_SERVER_LOCAL_STORAGE_PATH = os.path.join(DATA_DIR, "file_server")
_DAG_DEFINITION_DIR = os.path.join(ROOT_PATH, "examples/awel")
# Global language setting
LOCALES_DIR = os.path.join(ROOT_PATH, "i18n/locales")

current_directory = os.getcwd()


@cache
def get_device() -> str:
    try:
        import torch

        return (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
    except ModuleNotFoundError:
        return "cpu"


LLM_MODEL_CONFIG = {
    "flan-t5-base": os.path.join(MODEL_PATH, "flan-t5-base"),
    "vicuna-13b": os.path.join(MODEL_PATH, "vicuna-13b"),
    "vicuna-7b": os.path.join(MODEL_PATH, "vicuna-7b"),
    # (Llama2 based) see https://huggingface.co/lmsys/vicuna-13b-v1.5
    "vicuna-13b-v1.5": os.path.join(MODEL_PATH, "vicuna-13b-v1.5"),
    "vicuna-7b-v1.5": os.path.join(MODEL_PATH, "vicuna-7b-v1.5"),
    "codegen2-1b": os.path.join(MODEL_PATH, "codegen2-1B"),
    "codet5p-2b": os.path.join(MODEL_PATH, "codet5p-2b"),
    "chatglm-6b-int4": os.path.join(MODEL_PATH, "chatglm-6b-int4"),
    "chatglm-6b": os.path.join(MODEL_PATH, "chatglm-6b"),
    "chatglm2-6b": os.path.join(MODEL_PATH, "chatglm2-6b"),
    "chatglm2-6b-int4": os.path.join(MODEL_PATH, "chatglm2-6b-int4"),
    # https://huggingface.co/THUDM/chatglm3-6b
    "chatglm3-6b": os.path.join(MODEL_PATH, "chatglm3-6b"),
    # https://huggingface.co/THUDM/glm-4-9b-chat
    "glm-4-9b-chat": os.path.join(MODEL_PATH, "glm-4-9b-chat"),
    "glm-4-9b-chat-1m": os.path.join(MODEL_PATH, "glm-4-9b-chat-1m"),
    # https://huggingface.co/THUDM/codegeex4-all-9b
    "codegeex4-all-9b": os.path.join(MODEL_PATH, "codegeex4-all-9b"),
    "guanaco-33b-merged": os.path.join(MODEL_PATH, "guanaco-33b-merged"),
    "falcon-40b": os.path.join(MODEL_PATH, "falcon-40b"),
    "gorilla-7b": os.path.join(MODEL_PATH, "gorilla-7b"),
    "gptj-6b": os.path.join(MODEL_PATH, "ggml-gpt4all-j-v1.3-groovy.bin"),
    "proxyllm": "chatgpt_proxyllm",
    "chatgpt_proxyllm": "chatgpt_proxyllm",
    "bard_proxyllm": "bard_proxyllm",
    "claude_proxyllm": "claude_proxyllm",
    "wenxin_proxyllm": "wenxin_proxyllm",
    "tongyi_proxyllm": "tongyi_proxyllm",
    "zhipu_proxyllm": "zhipu_proxyllm",
    "gemini_proxyllm": "gemini_proxyllm",
    "bc_proxyllm": "bc_proxyllm",
    "spark_proxyllm": "spark_proxyllm",
    # https://platform.lingyiwanwu.com/docs/
    "yi_proxyllm": "yi_proxyllm",
    # https://platform.moonshot.cn/docs/
    "moonshot_proxyllm": "moonshot_proxyllm",
    "ollama_proxyllm": "ollama_proxyllm",
    # https://platform.deepseek.com/api-docs/
    "deepseek_proxyllm": "deepseek_proxyllm",
    "llama-2-7b": os.path.join(MODEL_PATH, "Llama-2-7b-chat-hf"),
    "llama-2-13b": os.path.join(MODEL_PATH, "Llama-2-13b-chat-hf"),
    "llama-2-70b": os.path.join(MODEL_PATH, "Llama-2-70b-chat-hf"),
    # https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct
    "meta-llama-3-8b-instruct": os.path.join(MODEL_PATH, "Meta-Llama-3-8B-Instruct"),
    # https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct
    "meta-llama-3-70b-instruct": os.path.join(MODEL_PATH, "Meta-Llama-3-70B-Instruct"),
    "meta-llama-3.1-8b-instruct": os.path.join(
        MODEL_PATH, "Meta-Llama-3.1-8B-Instruct"
    ),
    "meta-llama-3.1-70b-instruct": os.path.join(
        MODEL_PATH, "Meta-Llama-3.1-70B-Instruct"
    ),
    "meta-llama-3.1-405b-instruct": os.path.join(
        MODEL_PATH, "Meta-Llama-3.1-405B-Instruct"
    ),
    "baichuan-13b": os.path.join(MODEL_PATH, "Baichuan-13B-Chat"),
    # please rename "fireballoon/baichuan-vicuna-chinese-7b" to "baichuan-7b"
    "baichuan-7b": os.path.join(MODEL_PATH, "baichuan-7b"),
    "baichuan2-7b": os.path.join(MODEL_PATH, "Baichuan2-7B-Chat"),
    "baichuan2-13b": os.path.join(MODEL_PATH, "Baichuan2-13B-Chat"),
    # https://huggingface.co/Qwen/Qwen-7B-Chat
    "qwen-7b-chat": os.path.join(MODEL_PATH, "Qwen-7B-Chat"),
    # https://huggingface.co/Qwen/Qwen-7B-Chat-Int8
    "qwen-7b-chat-int8": os.path.join(MODEL_PATH, "Qwen-7B-Chat-Int8"),
    # https://huggingface.co/Qwen/Qwen-7B-Chat-Int4
    "qwen-7b-chat-int4": os.path.join(MODEL_PATH, "Qwen-7B-Chat-Int4"),
    # https://huggingface.co/Qwen/Qwen-14B-Chat
    "qwen-14b-chat": os.path.join(MODEL_PATH, "Qwen-14B-Chat"),
    # https://huggingface.co/Qwen/Qwen-14B-Chat-Int8
    "qwen-14b-chat-int8": os.path.join(MODEL_PATH, "Qwen-14B-Chat-Int8"),
    # https://huggingface.co/Qwen/Qwen-14B-Chat-Int4
    "qwen-14b-chat-int4": os.path.join(MODEL_PATH, "Qwen-14B-Chat-Int4"),
    # https://huggingface.co/Qwen/Qwen-72B-Chat
    "qwen-72b-chat": os.path.join(MODEL_PATH, "Qwen-72B-Chat"),
    # https://huggingface.co/Qwen/Qwen-72B-Chat-Int8
    "qwen-72b-chat-int8": os.path.join(MODEL_PATH, "Qwen-72B-Chat-Int8"),
    # https://huggingface.co/Qwen/Qwen-72B-Chat-Int4
    "qwen-72b-chat-int4": os.path.join(MODEL_PATH, "Qwen-72B-Chat-Int4"),
    # https://huggingface.co/Qwen/Qwen-1_8B-Chat
    "qwen-1.8b-chat": os.path.join(MODEL_PATH, "Qwen-1_8B-Chat"),
    # https://huggingface.co/Qwen/Qwen-1_8B-Chat-Int8
    "qwen-1.8b-chat-int8": os.path.join(MODEL_PATH, "wen-1_8B-Chat-Int8"),
    # https://huggingface.co/Qwen/Qwen-1_8B-Chat-Int4
    "qwen-1.8b-chat-int4": os.path.join(MODEL_PATH, "Qwen-1_8B-Chat-Int4"),
    # https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat
    "qwen1.5-1.8b-chat": os.path.join(MODEL_PATH, "Qwen1.5-1.8B-Chat"),
    "qwen1.5-7b-chat": os.path.join(MODEL_PATH, "Qwen1.5-7B-Chat"),
    "qwen1.5-14b-chat": os.path.join(MODEL_PATH, "Qwen1.5-14B-Chat"),
    # https://huggingface.co/Qwen/Qwen1.5-32B-Chat
    "qwen1.5-32b-chat": os.path.join(MODEL_PATH, "Qwen1.5-32B-Chat"),
    "qwen1.5-72b-chat": os.path.join(MODEL_PATH, "Qwen1.5-72B-Chat"),
    # https://huggingface.co/Qwen/Qwen1.5-110B-Chat
    "qwen1.5-110b-chat": os.path.join(MODEL_PATH, "Qwen1.5-110B-Chat"),
    # https://huggingface.co/Qwen/CodeQwen1.5-7B-Chat
    "codeqwen1.5-7b-chat": os.path.join(MODEL_PATH, "CodeQwen1.5-7B-Chat"),
    # https://huggingface.co/Qwen/Qwen1.5-MoE-A2.7B-Chat
    "qwen1.5-moe-a2.7b-chat": os.path.join(MODEL_PATH, "Qwen1.5-MoE-A2.7B-Chat"),
    "qwen2-57b-a14b-instruct": os.path.join(MODEL_PATH, "Qwen2-57B-A14B-Instruct"),
    "qwen2-57b-a14b-instruct-gptq-int4": os.path.join(
        MODEL_PATH, "Qwen2-57B-A14B-Instruct-GPTQ-Int4"
    ),
    "qwen2-72b-instruct": os.path.join(MODEL_PATH, "Qwen2-72B-Instruct"),
    "qwen2-72b-instruct-awq": os.path.join(MODEL_PATH, "Qwen2-72B-Instruct-AWQ"),
    "qwen2-72b-instruct-gptq-int8": os.path.join(
        MODEL_PATH, "Qwen2-72B-Instruct-GPTQ-Int8"
    ),
    "qwen2-72b-instruct-gptq-int4": os.path.join(
        MODEL_PATH, "Qwen2-72B-Instruct-GPTQ-Int4"
    ),
    "qwen2-7b-instruct": os.path.join(MODEL_PATH, "Qwen2-7B-Instruct"),
    "qwen2-7b-instruct-awq": os.path.join(MODEL_PATH, "Qwen2-7B-Instruct-AWQ"),
    "qwen2-7b-instruct-gptq-int8": os.path.join(
        MODEL_PATH, "Qwen2-7B-Instruct-GPTQ-Int8"
    ),
    "qwen2-7b-instruct-gptq-int4": os.path.join(
        MODEL_PATH, "Qwen2-7B-Instruct-GPTQ-Int4"
    ),
    "qwen2-1.5b-instruct": os.path.join(MODEL_PATH, "Qwen2-1.5B-Instruct"),
    "qwen2-1.5b-instruct-awq": os.path.join(MODEL_PATH, "Qwen2-1.5B-Instruct-AWQ"),
    "qwen2-1.5b-instruct-gptq-int8": os.path.join(
        MODEL_PATH, "Qwen2-1.5B-Instruct-GPTQ-Int8"
    ),
    "qwen2-1.5b-instruct-gptq-int4": os.path.join(
        MODEL_PATH, "Qwen2-1.5B-Instruct-GPTQ-Int4"
    ),
    "qwen2-0.5b-instruct": os.path.join(MODEL_PATH, "Qwen2-0.5B-Instruct"),
    "qwen2-0.5b-instruct-awq": os.path.join(MODEL_PATH, "Qwen2-0.5B-Instruct-AWQ"),
    "qwen2-0.5b-instruct-gptq-int8": os.path.join(
        MODEL_PATH, "Qwen2-0.5B-Instruct-GPTQ-Int8"
    ),
    "qwen2-0.5b-instruct-gptq-int4": os.path.join(
        MODEL_PATH, "Qwen2-0.5B-Instruct-GPTQ-Int4"
    ),
    "qwen2.5-0.5b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-0.5B-Instruct"),
    "qwen2.5-1.5b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-1.5B-Instruct"),
    "qwen2.5-3b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-3B-Instruct"),
    "qwen2.5-7b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-7B-Instruct"),
    "qwen2.5-14b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-14B-Instruct"),
    "qwen2.5-32b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-32B-Instruct"),
    "qwen2.5-72b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-72B-Instruct"),
    "qwen2.5-coder-1.5b-instruct": os.path.join(
        MODEL_PATH, "Qwen2.5-Coder-1.5B-Instruct"
    ),
    "qwen2.5-coder-32b-instruct": os.path.join(
        MODEL_PATH, "Qwen2.5-Coder-32B-Instruct"
    ),
    "qwen2.5-coder-14b-instruct": os.path.join(
        MODEL_PATH, "Qwen2.5-Coder-14B-Instruct"
    ),
    "qwen2.5-coder-3b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-Coder-3B-Instruct"),
    "qwen2.5-coder-7b-instruct": os.path.join(MODEL_PATH, "Qwen2.5-Coder-7B-Instruct"),
    "qwen2.5-coder-1.5b-instruct": os.path.join(
        MODEL_PATH, "Qwen2.5-Coder-1.5B-Instruct"
    ),
    "qwen2.5-coder-0.5b-instruct": os.path.join(
        MODEL_PATH, "Qwen2.5-Coder-0.5B-Instruct"
    ),
    # (Llama2 based) We only support WizardLM-13B-V1.2 for now, which is trained from Llama-2 13b, see https://huggingface.co/WizardLM/WizardLM-13B-V1.2
    "wizardlm-13b": os.path.join(MODEL_PATH, "WizardLM-13B-V1.2"),
    # wget https://huggingface.co/TheBloke/vicuna-13B-v1.5-GGUF/resolve/main/vicuna-13b-v1.5.Q4_K_M.gguf -O models/ggml-model-q4_0.gguf
    "llama-cpp": os.path.join(MODEL_PATH, "ggml-model-q4_0.gguf"),
    # https://huggingface.co/internlm/internlm-chat-7b-v1_1, 7b vs 7b-v1.1: https://github.com/InternLM/InternLM/issues/288
    "internlm-7b": os.path.join(MODEL_PATH, "internlm-chat-7b"),
    "internlm-7b-8k": os.path.join(MODEL_PATH, "internlm-chat-7b-8k"),
    "internlm-20b": os.path.join(MODEL_PATH, "internlm-chat-20b"),
    "internlm2_5-7b-chat": os.path.join(MODEL_PATH, "internlm2_5-7b-chat"),
    "internlm2_5-7b-chat-1m": os.path.join(MODEL_PATH, "internlm2_5-7b-chat-1m"),
    "codellama-7b": os.path.join(MODEL_PATH, "CodeLlama-7b-Instruct-hf"),
    "codellama-7b-sql-sft": os.path.join(MODEL_PATH, "codellama-7b-sql-sft"),
    "codellama-13b": os.path.join(MODEL_PATH, "CodeLlama-13b-Instruct-hf"),
    "codellama-13b-sql-sft": os.path.join(MODEL_PATH, "codellama-13b-sql-sft"),
    # For test now
    "opt-125m": os.path.join(MODEL_PATH, "opt-125m"),
    # https://huggingface.co/microsoft/Orca-2-7b
    "orca-2-7b": os.path.join(MODEL_PATH, "Orca-2-7b"),
    # https://huggingface.co/microsoft/Orca-2-13b
    "orca-2-13b": os.path.join(MODEL_PATH, "Orca-2-13b"),
    # https://huggingface.co/openchat/openchat_3.5
    "openchat-3.5": os.path.join(MODEL_PATH, "openchat_3.5"),
    # https://huggingface.co/openchat/openchat-3.5-1210
    "openchat-3.5-1210": os.path.join(MODEL_PATH, "openchat-3.5-1210"),
    "openchat-3.6-8b-20240522": os.path.join(MODEL_PATH, "openchat-3.6-8b-20240522"),
    # https://huggingface.co/hfl/chinese-alpaca-2-7b
    "chinese-alpaca-2-7b": os.path.join(MODEL_PATH, "chinese-alpaca-2-7b"),
    # https://huggingface.co/hfl/chinese-alpaca-2-13b
    "chinese-alpaca-2-13b": os.path.join(MODEL_PATH, "chinese-alpaca-2-13b"),
    # https://huggingface.co/THUDM/codegeex2-6b
    "codegeex2-6b": os.path.join(MODEL_PATH, "codegeex2-6b"),
    # https://huggingface.co/HuggingFaceH4/zephyr-7b-alpha
    "zephyr-7b-alpha": os.path.join(MODEL_PATH, "zephyr-7b-alpha"),
    # https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.1
    "mistral-7b-instruct-v0.1": os.path.join(MODEL_PATH, "Mistral-7B-Instruct-v0.1"),
    # https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1
    "mixtral-8x7b-instruct-v0.1": os.path.join(
        MODEL_PATH, "Mixtral-8x7B-Instruct-v0.1"
    ),
    "mistral-nemo-instruct-2407": os.path.join(
        MODEL_PATH, "Mistral-Nemo-Instruct-2407"
    ),
    # https://huggingface.co/upstage/SOLAR-10.7B-Instruct-v1.0
    "solar-10.7b-instruct-v1.0": os.path.join(MODEL_PATH, "SOLAR-10.7B-Instruct-v1.0"),
    # https://huggingface.co/Open-Orca/Mistral-7B-OpenOrca
    "mistral-7b-openorca": os.path.join(MODEL_PATH, "Mistral-7B-OpenOrca"),
    # https://huggingface.co/Xwin-LM/Xwin-LM-7B-V0.1
    "xwin-lm-7b-v0.1": os.path.join(MODEL_PATH, "Xwin-LM-7B-V0.1"),
    # https://huggingface.co/Xwin-LM/Xwin-LM-13B-V0.1
    "xwin-lm-13b-v0.1": os.path.join(MODEL_PATH, "Xwin-LM-13B-V0.1"),
    # https://huggingface.co/Xwin-LM/Xwin-LM-70B-V0.1
    "xwin-lm-70b-v0.1": os.path.join(MODEL_PATH, "Xwin-LM-70B-V0.1"),
    # https://huggingface.co/01-ai/Yi-34B-Chat
    "yi-34b-chat": os.path.join(MODEL_PATH, "Yi-34B-Chat"),
    # https://huggingface.co/01-ai/Yi-34B-Chat-8bits
    "yi-34b-chat-8bits": os.path.join(MODEL_PATH, "Yi-34B-Chat-8bits"),
    # https://huggingface.co/01-ai/Yi-34B-Chat-4bits
    "yi-34b-chat-4bits": os.path.join(MODEL_PATH, "Yi-34B-Chat-4bits"),
    "yi-6b-chat": os.path.join(MODEL_PATH, "Yi-6B-Chat"),
    # https://huggingface.co/01-ai/Yi-1.5-6B-Chat
    "yi-1.5-6b-chat": os.path.join(MODEL_PATH, "Yi-1.5-6B-Chat"),
    "yi-1.5-9b-chat": os.path.join(MODEL_PATH, "Yi-1.5-9B-Chat"),
    "yi-1.5-9b-chat-16k": os.path.join(MODEL_PATH, "Yi-1.5-9B-Chat-16K"),
    "yi-1.5-34b-chat": os.path.join(MODEL_PATH, "Yi-1.5-34B-Chat"),
    "yi-1.5-34b-chat-16k": os.path.join(MODEL_PATH, "Yi-1.5-34B-Chat-16K"),
    # https://huggingface.co/google/gemma-7b-it
    "gemma-7b-it": os.path.join(MODEL_PATH, "gemma-7b-it"),
    # https://huggingface.co/google/gemma-2b-it
    "gemma-2b-it": os.path.join(MODEL_PATH, "gemma-2b-it"),
    "gemma-2-2b-it": os.path.join(MODEL_PATH, "gemma-2-2b-it"),
    "gemma-2-9b-it": os.path.join(MODEL_PATH, "gemma-2-9b-it"),
    "gemma-2-27b-it": os.path.join(MODEL_PATH, "gemma-2-27b-it"),
    "starling-lm-7b-beta": os.path.join(MODEL_PATH, "Starling-LM-7B-beta"),
    "deepseek-v2-lite-chat": os.path.join(MODEL_PATH, "DeepSeek-V2-Lite-Chat"),
    "deepseek-coder-v2-instruct": os.path.join(
        MODEL_PATH, "DeepSeek-Coder-V2-Instruct"
    ),
    "deepseek-coder-v2-lite-instruct": os.path.join(
        MODEL_PATH, "DeepSeek-Coder-V2-Lite-Instruct"
    ),
    "sailor-14b-chat": os.path.join(MODEL_PATH, "Sailor-14B-Chat"),
    # https://huggingface.co/microsoft/Phi-3-medium-128k-instruct
    "phi-3-medium-128k-instruct": os.path.join(
        MODEL_PATH, "Phi-3-medium-128k-instruct"
    ),
    "phi-3-medium-4k-instruct": os.path.join(MODEL_PATH, "Phi-3-medium-4k-instruct"),
    "phi-3-small-128k-instruct": os.path.join(MODEL_PATH, "Phi-3-small-128k-instruct"),
    "phi-3-small-8k-instruct": os.path.join(MODEL_PATH, "Phi-3-small-8k-instruct"),
    "phi-3-mini-128k-instruct": os.path.join(MODEL_PATH, "Phi-3-mini-128k-instruct"),
    "phi-3-mini-4k-instruct": os.path.join(MODEL_PATH, "Phi-3-mini-4k-instruct"),
    "llama-3-sqlcoder-8b": os.path.join(MODEL_PATH, "llama-3-sqlcoder-8b"),
}

EMBEDDING_MODEL_CONFIG = {
    "text2vec": os.path.join(MODEL_PATH, "text2vec-large-chinese"),
    "text2vec-base": os.path.join(MODEL_PATH, "text2vec-base-chinese"),
    # https://huggingface.co/moka-ai/m3e-large
    "m3e-base": os.path.join(MODEL_PATH, "m3e-base"),
    # https://huggingface.co/moka-ai/m3e-base
    "m3e-large": os.path.join(MODEL_PATH, "m3e-large"),
    # https://huggingface.co/BAAI/bge-large-en
    "bge-large-en": os.path.join(MODEL_PATH, "bge-large-en"),
    "bge-base-en": os.path.join(MODEL_PATH, "bge-base-en"),
    # https://huggingface.co/BAAI/bge-large-zh
    "bge-large-zh": os.path.join(MODEL_PATH, "bge-large-zh"),
    "bge-base-zh": os.path.join(MODEL_PATH, "bge-base-zh"),
    # https://huggingface.co/BAAI/bge-m3, beg need normalize_embeddings=True
    "bge-m3": os.path.join(MODEL_PATH, "bge-m3"),
    "gte-large-zh": os.path.join(MODEL_PATH, "gte-large-zh"),
    "gte-base-zh": os.path.join(MODEL_PATH, "gte-base-zh"),
    "sentence-transforms": os.path.join(MODEL_PATH, "all-MiniLM-L6-v2"),
    "proxy_openai": "proxy_openai",
    "proxy_azure": "proxy_azure",
    # Common HTTP embedding model
    "proxy_http_openapi": "proxy_http_openapi",
    "proxy_ollama": "proxy_ollama",
    "proxy_tongyi": "proxy_tongyi",
    "proxy_qianfan": "proxy_qianfan",
    # Rerank model, rerank mode is a special embedding model
    "bge-reranker-base": os.path.join(MODEL_PATH, "bge-reranker-base"),
    "bge-reranker-large": os.path.join(MODEL_PATH, "bge-reranker-large"),
    # Proxy rerank model
    "rerank_proxy_http_openapi": "rerank_proxy_http_openapi",
}


KNOWLEDGE_UPLOAD_ROOT_PATH = DATA_DIR
