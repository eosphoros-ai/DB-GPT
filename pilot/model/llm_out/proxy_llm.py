#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from pilot.configs.config import Config

from pilot.model.proxy.llms.chatgpt import chatgpt_generate_stream
from pilot.model.proxy.llms.bard import bard_generate_stream
from pilot.model.proxy.llms.claude import claude_generate_stream
from pilot.model.proxy.llms.wenxin import wenxin_generate_stream
from pilot.model.proxy.llms.tongyi import tongyi_generate_stream
from pilot.model.proxy.llms.zhipu import zhipu_generate_stream

# from pilot.model.proxy.llms.gpt4 import gpt4_generate_stream

CFG = Config()


def proxyllm_generate_stream(model, tokenizer, params, device, context_len=2048):
    generator_mapping = {
        "proxyllm": chatgpt_generate_stream,
        "chatgpt_proxyllm": chatgpt_generate_stream,
        "bard_proxyllm": bard_generate_stream,
        "claude_proxyllm": claude_generate_stream,
        # "gpt4_proxyllm": gpt4_generate_stream, move to chatgpt_generate_stream
        "wenxin_proxyllm": wenxin_generate_stream,
        "tongyi_proxyllm": tongyi_generate_stream,
        "zhipu_proxyllm": zhipu_generate_stream,
    }

    default_error_message = f"{CFG.LLM_MODEL} LLM is not supported"
    generator_function = generator_mapping.get(
        CFG.LLM_MODEL, lambda: default_error_message
    )

    yield from generator_function(model, tokenizer, params, device, context_len)
