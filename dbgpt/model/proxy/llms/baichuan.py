import hashlib
import json
import time
import requests
from typing import List
from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType

BAICHUAN_DEFAULT_MODEL = "Baichuan2-53B"


def _calculate_md5(text: str) -> str:
    """Calculate md5"""
    md5 = hashlib.md5()
    md5.update(text.encode("utf-8"))
    encrypted = md5.hexdigest()
    return encrypted


def _sign(data: dict, secret_key: str, timestamp: str):
    data_str = json.dumps(data)
    signature = _calculate_md5(secret_key + data_str + timestamp)
    return signature


def baichuan_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=4096
):
    model_params = model.get_params()
    url = "https://api.baichuan-ai.com/v1/stream/chat"

    model_name = model_params.proxyllm_backend or BAICHUAN_DEFAULT_MODEL
    proxy_api_key = model_params.proxy_api_key
    proxy_api_secret = model_params.proxy_api_secret

    history = []
    messages: List[ModelMessage] = params["messages"]
    # Add history conversation
    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "system", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": "message.content"})
        else:
            pass

    payload = {
        "model": model_name,
        "messages": history,
        "parameters": {
            "temperature": params.get("temperature"),
            "top_k": params.get("top_k", 10),
        },
    }

    timestamp = int(time.time())
    _signature = _sign(payload, proxy_api_secret, str(timestamp))

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + proxy_api_key,
        "X-BC-Request-Id": params.get("request_id") or "dbgpt",
        "X-BC-Timestamp": str(timestamp),
        "X-BC-Signature": _signature,
        "X-BC-Sign-Algo": "MD5",
    }

    res = requests.post(url=url, json=payload, headers=headers, stream=True)
    print(f"Send request to {url} with real model {model_name}")

    text = ""
    for line in res.iter_lines():
        if line:
            if not line.startswith(b"data: "):
                error_message = line.decode("utf-8")
                yield error_message
            else:
                json_data = line.split(b": ", 1)[1]
                decoded_line = json_data.decode("utf-8")
                if decoded_line.lower() != "[DONE]".lower():
                    obj = json.loads(json_data)
                    if obj["data"]["messages"][0].get("content") is not None:
                        content = obj["data"]["messages"][0].get("content")
                        text += content
                yield text
