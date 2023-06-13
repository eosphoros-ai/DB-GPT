#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from functools import cache
from typing import List
from pilot.model.llm_out.vicuna_base_llm import generate_stream


class BaseChatAdpter:
    """The Base class for chat with llm models. it will match the model,
    and fetch output from model"""

    def match(self, model_path: str):
        return True

    def get_generate_stream_func(self):
        """Return the generate stream handler func"""
        pass


llm_model_chat_adapters: List[BaseChatAdpter] = []


def register_llm_model_chat_adapter(cls):
    """Register a chat adapter"""
    llm_model_chat_adapters.append(cls())


@cache
def get_llm_chat_adapter(model_path: str) -> BaseChatAdpter:
    """Get a chat generate func for a model"""
    for adapter in llm_model_chat_adapters:
        if adapter.match(model_path):
            return adapter

    raise ValueError(f"Invalid model for chat adapter {model_path}")


class VicunaChatAdapter(BaseChatAdpter):
    """Model chat Adapter for vicuna"""

    def match(self, model_path: str):
        return "vicuna" in model_path

    def get_generate_stream_func(self):
        return generate_stream


class ChatGLMChatAdapter(BaseChatAdpter):
    """Model chat Adapter for ChatGLM"""

    def match(self, model_path: str):
        return "chatglm" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.chatglm_llm import chatglm_generate_stream

        return chatglm_generate_stream


class CodeT5ChatAdapter(BaseChatAdpter):
    """Model chat adapter for CodeT5"""

    def match(self, model_path: str):
        return "codet5" in model_path

    def get_generate_stream_func(self):
        # TODO
        pass


class CodeGenChatAdapter(BaseChatAdpter):
    """Model chat adapter for CodeGen"""

    def match(self, model_path: str):
        return "codegen" in model_path

    def get_generate_stream_func(self):
        # TODO
        pass


class GuanacoChatAdapter(BaseChatAdpter):
    """Model chat adapter for Guanaco"""

    def match(self, model_path: str):
        return "guanaco" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.guanaco_llm import guanaco_generate_stream

        return guanaco_generate_stream


class FalconChatAdapter(BaseChatAdpter):
    """Model chat adapter for Guanaco"""

    def match(self, model_path: str):
        return "falcon" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.falcon_llm import falcon_generate_output

        return falcon_generate_output


class ProxyllmChatAdapter(BaseChatAdpter):
    def match(self, model_path: str):
        return "proxyllm" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.proxy_llm import proxyllm_generate_stream

        return proxyllm_generate_stream


class GorillaChatAdapter(BaseChatAdpter):
    def match(self, model_path: str):
        return "gorilla" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.gorilla_llm import generate_stream

        return generate_stream


class GPT4AllChatAdapter(BaseChatAdpter):
    def match(self, model_path: str):
        return "gpt4all" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.gpt4all_llm import gpt4all_generate_stream

        return gpt4all_generate_stream


register_llm_model_chat_adapter(VicunaChatAdapter)
register_llm_model_chat_adapter(ChatGLMChatAdapter)
register_llm_model_chat_adapter(GuanacoChatAdapter)
register_llm_model_chat_adapter(FalconChatAdapter)
register_llm_model_chat_adapter(GorillaChatAdapter)
register_llm_model_chat_adapter(GPT4AllChatAdapter)

# Proxy model for test and develop, it's cheap for us now.
register_llm_model_chat_adapter(ProxyllmChatAdapter)

register_llm_model_chat_adapter(BaseChatAdpter)
