#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import TypedDict


class Message(TypedDict):
    """LLM Message object containing usually like (role: content)"""

    role: str
    content: str
