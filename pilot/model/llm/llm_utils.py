#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Optional
from pilot.model.llm.base import Message
from pilot.configs.config import Config

# Overly simple abstraction util we create something better
# simple retry mechanism when getting a rate error or a bad gateway
def create_chat_competion(
    messages: List[Message],
    model: Optional[str] = None,
    temperature: float = None,
    max_tokens: Optional[int] = None,
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
    