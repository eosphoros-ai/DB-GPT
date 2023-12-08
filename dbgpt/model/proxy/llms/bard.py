import requests
from typing import List
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.model.proxy.llms.proxy_model import ProxyModel


def bard_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    proxy_api_key = model_params.proxy_api_key
    proxy_server_url = model_params.proxy_server_url

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

    if proxy_server_url is not None:
        headers = {"Content-Type": "application/json"}
        payloads = {"input": "\n".join(msgs)}
        response = requests.post(
            proxy_server_url, headers=headers, json=payloads, stream=False
        )
        if response.ok:
            yield response.text
        else:
            yield f"bard proxy url request failed!, response = {str(response)}"
    else:
        import bardapi

        response = bardapi.core.Bard(proxy_api_key).get_answer("\n".join(msgs))

        if response is not None and response.get("content") is not None:
            yield str(response["content"])
        else:
            yield f"bard response error: {str(response)}"
