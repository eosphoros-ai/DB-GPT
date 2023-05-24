#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import abc
import functools
import time
from typing import Optional

from pilot.configs.config import Config
from pilot.conversation import (
    Conversation,
    auto_dbgpt_one_shot,
    conv_one_shot,
    conv_templates,
)
from pilot.model.llm.base import Message


# TODO Rewrite this
def retry_stream_api(
    num_retries: int = 10, backoff_base: float = 2.0, warn_user: bool = True
):
    """Retry an Vicuna Server call.

    Args:
        num_retries int: Number of retries. Defaults to 10.
        backoff_base float: Base for exponential backoff. Defaults to 2.
        warn_user bool: Whether to warn the user. Defaults to True.
    """
    retry_limit_msg = f"Error: Reached rate limit, passing..."
    backoff_msg = f"Error: API Bad gateway. Waiting {{backoff}} seconds..."

    def _wrapper(func):
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            user_warned = not warn_user
            num_attempts = num_retries + 1  # +1 for the first attempt
            for attempt in range(1, num_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if (e.http_status != 502) or (attempt == num_attempts):
                        raise

                backoff = backoff_base ** (attempt + 2)
                time.sleep(backoff)

        return _wrapped

    return _wrapper


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
    # convert vicuna message to chat completion.
    for plugin in cfg.plugins:
        if plugin.can_handle_chat_completion():
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
