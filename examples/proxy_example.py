#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dashscope
import requests
import hashlib
from http import HTTPStatus
from dashscope import Generation


def call_with_messages():
    messages = [
        {"role": "system", "content": "你是生活助手机器人。"},
        {"role": "user", "content": "如何做西红柿鸡蛋？"},
    ]
    gen = Generation()
    response = gen.call(
        Generation.Models.qwen_turbo,
        messages=messages,
        stream=True,
        top_p=0.8,
        result_format="message",  # set the result to be "message" format.
    )

    for response in response:
        # The response status_code is HTTPStatus.OK indicate success,
        # otherwise indicate request is failed, you can get error code
        # and message from code and message.
        if response.status_code == HTTPStatus.OK:
            print(response.output)  # The output text
            print(response.usage)  # The usage information
        else:
            print(response.code)  # The error code.
            print(response.message)  # The error message.


def build_access_token(api_key: str, secret_key: str) -> str:
    """
    Generate Access token according AK, SK
    """

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }

    res = requests.get(url=url, params=params)

    if res.status_code == 200:
        return res.json().get("access_token")


def _calculate_md5(text: str) -> str:
    md5 = hashlib.md5()
    md5.update(text.encode("utf-8"))
    encrypted = md5.hexdigest()
    return encrypted


def baichuan_call():
    url = "https://api.baichuan-ai.com/v1/stream/chat"


if __name__ == "__main__":
    call_with_messages()
