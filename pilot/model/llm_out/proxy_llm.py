#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from pilot.configs.config import Config

from pilot.model.proxy.proxy_llms.chatgpt import chatgpt_generate_stream
from pilot.model.proxy.proxy_llms.bard import bard_generate_stream
from pilot.model.proxy.proxy_llms.claude import claude_generate_stream
from pilot.model.proxy.proxy_llms.wenxin import wenxin_generate_stream
from pilot.model.proxy.proxy_llms.tongyi import tongyi_generate_stream
from pilot.model.proxy.proxy_llms.gpt4 import gpt4_generate_stream

CFG = Config()


def proxyllm_generate_stream(model, tokenizer, params, device, context_len=2048):
    generator_mapping = {
        "chatgpt": chatgpt_generate_stream,
        "bard": bard_generate_stream,
        "claude": claude_generate_stream,
        "gpt4": gpt4_generate_stream,
        "wenxin": wenxin_generate_stream,
        "tongyi": tongyi_generate_stream,
    }

    default_error_message = f"{CFG.PROXY_MODEL} LLM is not supported"
    generator_function = generator_mapping.get(
        CFG.PROXY_MODEL, lambda: default_error_message
    )

    yield from generator_function(model, tokenizer, params, device, context_len)
