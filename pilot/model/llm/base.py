#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import TypedDict


class Message(TypedDict):
    """Vicuna Message object containing a role and the message content"""

    role: str
    content: str


@dataclass
class ModelInfo:
    """Struct for model information.

    Would be lovely to eventually get this directly from APIs
    """

    name: str
    max_tokens: int


@dataclass
class LLMResponse:
    """Standard response struct for a response from a LLM model."""

    model_info = ModelInfo


@dataclass
class ChatModelResponse(LLMResponse):
    """Standard response struct for a response from an LLM model."""

    content: str = None
