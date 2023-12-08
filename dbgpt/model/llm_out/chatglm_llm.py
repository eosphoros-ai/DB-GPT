#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from typing import List
import re

import torch

from dbgpt.app.scene import ModelMessage, _parse_model_messages

# TODO move sep to scene prompt of model
_CHATGLM_SEP = "\n"
_CHATGLM2_SEP = "\n\n"


@torch.inference_mode()
def chatglm_generate_stream(
    model, tokenizer, params, device, context_len=2048, stream_interval=2
):
    """Generate text using chatglm model's chat api_v1"""
    prompt = params["prompt"]
    temperature = float(params.get("temperature", 1.0))
    top_p = float(params.get("top_p", 1.0))
    stop = params.get("stop", "###")
    echo = params.get("echo", False)

    generate_kwargs = {
        "do_sample": True if temperature > 1e-5 else False,
        "top_p": top_p,
        "repetition_penalty": 1.0,
        "logits_processor": None,
    }

    if temperature > 1e-5:
        generate_kwargs["temperature"] = temperature

    # TODO, Fix this
    # print(prompt)
    # messages = prompt.split(stop)
    messages: List[ModelMessage] = params["messages"]
    query, system_messages, hist = _parse_model_messages(messages)
    system_messages_str = "".join(system_messages)
    if not hist:
        # No history conversation, but has system messages, merge to user`s query
        query = prompt_adaptation(system_messages_str, query)
    else:
        # history exist, add system message to head of history
        hist[0][0] = system_messages_str + _CHATGLM2_SEP + hist[0][0]

    print("Query Message: ", query)
    print("hist: ", hist)

    for i, (response, new_hist) in enumerate(
        model.stream_chat(tokenizer, query, hist, **generate_kwargs)
    ):
        if echo:
            output = query + " " + response
        else:
            output = response

        yield output

    yield output


class HistoryEntry:
    def __init__(self, question: str = "", answer: str = ""):
        self.question = question
        self.answer = answer

    def add_question(self, question: str):
        self.question += question

    def add_answer(self, answer: str):
        self.answer += answer

    def to_list(self):
        if self.question == "" or self.answer == "":
            return None
        return [self.question, self.answer]


def build_history(hist: List[HistoryEntry]) -> List[List[str]]:
    return list(filter(lambda hl: hl is not None, map(lambda h: h.to_list(), hist)))


def prompt_adaptation(system_messages_str: str, human_message: str) -> str:
    if not system_messages_str or system_messages_str == "":
        return human_message
    # TODO Multi-model prompt adaptation
    adaptation_rules = [
        r"Question:\s*{}\s*",  # chat_db scene
        r"Goals:\s*{}\s*",  # chat_execution
        r"问题:\s*{}\s*",  # chat_knowledge zh
        r"question:\s*{}\s*",  # chat_knowledge en
    ]
    # system message has include human question
    for rule in adaptation_rules:
        pattern = re.compile(rule.format(re.escape(human_message)))
        if re.search(pattern, system_messages_str):
            return system_messages_str
    # https://huggingface.co/THUDM/chatglm2-6b/blob/e186c891cf64310ac66ef10a87e6635fa6c2a579/modeling_chatglm.py#L926
    return system_messages_str + _CHATGLM2_SEP + human_message
