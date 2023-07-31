import bardapi
import requests
from typing import List
from pilot.configs.config import Config
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType

CFG = Config()


def bard_generate_stream(model, tokenizer, params, device, context_len=2048):
    history = []
    messages: List[ModelMessage] = params["messages"]
    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "system", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
        else:
            pass

    temp_his = history[::-1]
    last_user_input = None
    for m in temp_his:
        if m["role"] == "user":
            last_user_input = m
            break
    if last_user_input:
        history.remove(last_user_input)
        history.append(last_user_input)

    msgs = []
    for msg in history:
        if msg.get("content"):
            msgs.append(msg["content"])

    if CFG.proxy_server_url is not None:
        headers = {"Content-Type": "application/json"}
        payloads = {"input": "\n".join(msgs)}
        response = requests.post(
            CFG.proxy_server_url, headers=headers, json=payloads, stream=False
        )
        if response.ok:
            yield response.text
        else:
            yield f"bard proxy url request failed!, response = {str(response)}"
    else:
        response = bardapi.core.Bard(CFG.bard_proxy_api_key).get_answer("\n".join(msgs))

        if response is not None and response.get("content") is not None:
            yield str(response["content"])
        else:
            yield f"bard response error: {str(response)}"
