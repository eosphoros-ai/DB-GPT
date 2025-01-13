"""
This code file will be deprecated in the future.
We have integrated fastchat. For details, see: dbgpt/model/model_adapter.py
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from functools import cache
from typing import Dict, List, Tuple

from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.model.llm.conversation import Conversation, get_conv_template


class BaseChatAdpter:
    """The Base class for chat with llm models. it will match the model,
    and fetch output from model"""

    def match(self, model_path: str):
        return False

    def get_generate_stream_func(self, model_path: str):
        """Return the generate stream handler func"""
        from dbgpt.model.llm.inference import generate_stream

        return generate_stream

    def get_conv_template(self, model_path: str) -> Conversation:
        return None

    def model_adaptation(
        self, params: Dict, model_path: str, prompt_template: str = None
    ) -> Tuple[Dict, Dict]:
        """Params adaptation"""
        conv = self.get_conv_template(model_path)
        messages = params.get("messages")
        # Some model scontext to dbgpt server
        model_context = {"prompt_echo_len_char": -1}

        if messages:
            # Dict message to ModelMessage
            messages = [
                m if isinstance(m, ModelMessage) else ModelMessage(**m)
                for m in messages
            ]
            params["messages"] = messages

        if prompt_template:
            print(f"Use prompt template {prompt_template} from config")
            conv = get_conv_template(prompt_template)

        if not conv or not messages:
            # Nothing to do
            print(
                f"No conv from model_path {model_path} or no messages in params, {self}"
            )
            return params, model_context
        conv = conv.copy()
        system_messages = []
        for message in messages:
            role, content = None, None
            if isinstance(message, ModelMessage):
                role = message.role
                content = message.content
            elif isinstance(message, dict):
                role = message["role"]
                content = message["content"]
            else:
                raise ValueError(f"Invalid message type: {message}")

            if role == ModelMessageRoleType.SYSTEM:
                # Support for multiple system messages
                system_messages.append(content)
            elif role == ModelMessageRoleType.HUMAN:
                conv.append_message(conv.roles[0], content)
            elif role == ModelMessageRoleType.AI:
                conv.append_message(conv.roles[1], content)
            else:
                raise ValueError(f"Unknown role: {role}")
        if system_messages:
            conv.update_system_message("".join(system_messages))
        # Add a blank message for the assistant.
        conv.append_message(conv.roles[1], None)
        new_prompt = conv.get_prompt()
        # Overwrite the original prompt
        # TODO remote bos token and eos token from tokenizer_config.json of model
        prompt_echo_len_char = len(new_prompt.replace("</s>", "").replace("<s>", ""))
        model_context["prompt_echo_len_char"] = prompt_echo_len_char
        model_context["echo"] = params.get("echo", True)
        params["prompt"] = new_prompt

        # Overwrite model params:
        params["stop"] = conv.stop_str

        return params, model_context


llm_model_chat_adapters: List[BaseChatAdpter] = []


def register_llm_model_chat_adapter(cls):
    """Register a chat adapter"""
    llm_model_chat_adapters.append(cls())


@cache
def get_llm_chat_adapter(model_name: str, model_path: str) -> BaseChatAdpter:
    """Get a chat generate func for a model"""
    for adapter in llm_model_chat_adapters:
        if adapter.match(model_name):
            print(f"Get model chat adapter with model name {model_name}, {adapter}")
            return adapter
    for adapter in llm_model_chat_adapters:
        if adapter.match(model_path):
            print(f"Get model chat adapter with model path {model_path}, {adapter}")
            return adapter
    raise ValueError(
        f"Invalid model for chat adapter with model name {model_name} and model path "
        f"{model_path}"
    )


class GPT4AllChatAdapter(BaseChatAdpter):
    def match(self, model_path: str):
        return "gptj-6b" in model_path

    def get_generate_stream_func(self, model_path: str):
        from dbgpt.model.llm_out.gpt4all_llm import gpt4all_generate_stream

        return gpt4all_generate_stream


class CodeLlamaChatAdapter(BaseChatAdpter):
    """The model ChatAdapter for codellama ."""

    def match(self, model_path: str):
        return "codellama" in model_path.lower()

    def get_conv_template(self, model_path: str) -> Conversation:
        return get_conv_template("codellama")


class LlamaCppChatAdapter(BaseChatAdpter):
    def match(self, model_path: str):
        from dbgpt.model.adapter.old_adapter import LlamaCppAdapater

        if "llama-cpp" == model_path:
            return True
        is_match, _ = LlamaCppAdapater._parse_model_path(model_path)
        return is_match

    def get_conv_template(self, model_path: str) -> Conversation:
        return get_conv_template("llama-2")

    def get_generate_stream_func(self, model_path: str):
        from dbgpt.model.llm_out.llama_cpp_llm import generate_stream

        return generate_stream


register_llm_model_chat_adapter(GPT4AllChatAdapter)
register_llm_model_chat_adapter(CodeLlamaChatAdapter)
register_llm_model_chat_adapter(LlamaCppChatAdapter)
# just for test_py, remove this later
register_llm_model_chat_adapter(BaseChatAdpter)
