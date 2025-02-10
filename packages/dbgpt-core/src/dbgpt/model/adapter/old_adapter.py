"""
This code file will be deprecated in the future.
We have integrated fastchat. For details, see: dbgpt/model/model_adapter.py
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import re
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from transformers import AutoModelForCausalLM, AutoTokenizer

from dbgpt._private.config import Config
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.model.adapter.template import ConversationAdapter, PromptType
from dbgpt.model.base import ModelType
from dbgpt.model.llm.conversation import Conversation
from dbgpt.model.parameter import (
    LlamaCppModelParameters,
    ModelParameters,
)

if TYPE_CHECKING:
    from dbgpt_app.chat_adapter import BaseChatAdpter

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
            raise NotImplementedError("Not support proxy model yet")
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
def get_llm_model_adapter(
    model_name: str, model_path: Optional[str] = None
) -> BaseLLMAdaper:
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


def auto_configure_device_map(num_gpus):
    """handling multi gpu calls"""
    # transformer.word_embeddings occupying 1 floors
    # transformer.final_layernorm and lm_head occupying 1 floors
    # transformer.layers occupying 28 floors
    # Allocate a total of 30 layers to number On gpus cards
    num_trans_layers = 28
    per_gpu_layers = 30 / num_gpus
    # Bugfix: call torch.embedding in Linux and the incoming weight and input are not
    # on the same device, resulting in a RuntimeError
    # Under Windows, model. device will be set to transformer. word_ Embeddings. device
    # Under Linux, model. device will be set to lm_ Head.device
    # When calling chat or stream_ During chat, input_ IDS will be placed on model.
    # device
    # If transformer. word_ If embeddings. device and model. device are different, it
    # will cause a RuntimeError
    # Therefore, here we will transform. word_ Embeddings, transformer. final_
    # Layernorm, lm_ Put all the heads on the first card
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


class CodeLlamaAdapter(BaseLLMAdaper):
    """The model adapter for codellama"""

    def match(self, model_path: str):
        return "codellama" in model_path.lower()

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        model, tokenizer = super().loader(model_path, from_pretrained_kwargs)
        model.config.eos_token_id = tokenizer.eos_token_id
        model.config.pad_token_id = tokenizer.pad_token_id
        return model, tokenizer


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
                f"Model path {model_path} is not single file, use first *gglm*.gguf "
                f"model file: {model_path}"
            )
        if not re.fullmatch(r".*ggml.*\.gguf", model_path):
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


class OldLLMModelAdapterWrapper(LLMModelAdapter):
    """Wrapping old adapter, which may be removed later"""

    def __init__(self, adapter: BaseLLMAdaper, chat_adapter: "BaseChatAdpter") -> None:
        self._adapter = adapter
        self._chat_adapter = chat_adapter

    def new_adapter(self, **kwargs) -> "LLMModelAdapter":
        return OldLLMModelAdapterWrapper(self._adapter, self._chat_adapter)

    def use_fast_tokenizer(self) -> bool:
        return self._adapter.use_fast_tokenizer()

    def model_type(self) -> str:
        return self._adapter.model_type()

    def model_param_class(self, model_type: str = None) -> ModelParameters:
        return self._adapter.model_param_class(model_type)

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        conv_template = self._chat_adapter.get_conv_template(model_path)
        return OldConversationAdapter(conv_template) if conv_template else None

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        return self._adapter.loader(model_path, from_pretrained_kwargs)

    def get_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        return self._chat_adapter.get_generate_stream_func(
            deploy_model_params.real_model_path
        )

    def __str__(self) -> str:
        return "{}({}.{})".format(
            self.__class__.__name__,
            self._adapter.__class__.__module__,
            self._adapter.__class__.__name__,
        )


class OldConversationAdapter(ConversationAdapter):
    """Wrapping old Conversation, which may be removed later"""

    def __init__(self, conv: Conversation) -> None:
        self._conv = conv

    @property
    def prompt_type(self) -> PromptType:
        return PromptType.DBGPT

    @property
    def roles(self) -> Tuple[str]:
        return self._conv.roles

    @property
    def sep(self) -> Optional[str]:
        return self._conv.sep

    @property
    def stop_str(self) -> str:
        return self._conv.stop_str

    @property
    def stop_token_ids(self) -> Optional[List[int]]:
        return self._conv.stop_token_ids

    def get_prompt(self) -> str:
        return self._conv.get_prompt()

    def set_system_message(self, system_message: str) -> None:
        self._conv.update_system_message(system_message)

    def append_message(self, role: str, message: str) -> None:
        self._conv.append_message(role, message)

    def update_last_message(self, message: str) -> None:
        self._conv.update_last_message(message)

    def copy(self) -> "ConversationAdapter":
        return OldConversationAdapter(self._conv.copy())


register_llm_model_adapters(GPT4AllAdapter)
register_llm_model_adapters(CodeLlamaAdapter)
register_llm_model_adapters(LlamaCppAdapater)
# just for test_py, remove this later
register_llm_model_adapters(BaseLLMAdaper)
