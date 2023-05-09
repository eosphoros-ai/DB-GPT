#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import abc
from typing import List, Optional
from pilot.model.llm.base import Message
from pilot.conversation import conv_templates, Conversation, conv_one_shot, auto_dbgpt_one_shot 
from pilot.configs.config import Config

# Overly simple abstraction util we create something better
# simple retry mechanism when getting a rate error or a bad gateway
def create_chat_competion(
    conv: Conversation,
    model: Optional[str] = None,
    temperature: float = None,
    max_new_tokens: Optional[int] = None,
) -> str:
    """Create a chat completion using the Vicuna-13b
    
        Args:
            messages(List[Message]): The messages to send to the chat completion
            model (str, optional): The model to use. Default to None.
            temperature (float, optional): The temperature to use. Defaults to 0.7.
            max_tokens (int, optional): The max tokens to use. Defaults to None.

        Returns:
            str: The response from the chat completion
    """
    cfg = Config()
    if temperature is None:
        temperature = cfg.temperature

    # TODO request vicuna model get response
    for plugin in cfg.plugins:
        pass


class ChatIO(abc.ABC):
    @abc.abstractmethod
    def prompt_for_input(self, role: str) -> str:
        """Prompt for input from a role."""
    
    @abc.abstractmethod
    def prompt_for_output(self, role: str) -> str:
        """Prompt for output from a role."""

    @abc.abstractmethod
    def stream_output(self, output_stream, skip_echo_len: int):
        """Stream output."""


class SimpleChatIO(ChatIO):
    def prompt_for_input(self, role: str) -> str:
        return input(f"{role}: ")

    def prompt_for_output(self, role: str) -> str:
        print(f"{role}: ", end="", flush=True)

    def stream_output(self, output_stream, skip_echo_len: int):
        pre = 0
        for outputs in output_stream:
            outputs = outputs[skip_echo_len:].strip()
            now = len(outputs) - 1
            if now > pre:
                print(" ".join(outputs[pre:now]), end=" ", flush=True)
                pre = now

        print(" ".join(outputs[pre:]), flush=True)
        return " ".join(outputs)

