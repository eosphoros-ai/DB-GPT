#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class BaseChatAdpter:
    """The Base class for chat with llm models. it will match the model,
    and fetch output from model"""

    def match(self, model_path: str):
        return True

    def get_generate_stream_func(self):
        pass