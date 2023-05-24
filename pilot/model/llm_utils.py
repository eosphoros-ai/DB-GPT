#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from typing import List, Optional

from pilot.configs.config import Config
from pilot.model.base import Message
from pilot.server.llmserver import generate_output


def create_chat_completion(
    messages: List[Message],  # type: ignore
    model: Optional[str] = None,
    temperature: float = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Create a chat completion using the vicuna local model

    Args:
       messages(List[Message]): The messages to send to the chat completion
       model (str, optional): The model to use. Defaults to None.
       temperature (float, optional): The temperature to use. Defaults to 0.7.
       max_tokens (int, optional): The max tokens to use. Defaults to None

     Returns:
        str: The response from chat completion
    """
    cfg = Config()
    if temperature is None:
        temperature = cfg.temperature

    for plugin in cfg.plugins:
        if plugin.can_handle_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            message = plugin.handle_chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if message is not None:
                return message

        response = None
        # TODO impl this use vicuna server api
