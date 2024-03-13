import json
from typing import List

import requests

from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

BAICHUAN_DEFAULT_MODEL = "Baichuan2-Turbo-192k"


def baichuan_generate_stream(
    model: ProxyModel, tokenizer=None, params=None, device=None, context_len=4096
):
    # TODO: Support new Baichuan ProxyLLMClient
    url = "https://api.baichuan-ai.com/v1/chat/completions"

    model_params = model.get_params()
    model_name = model_params.proxyllm_backend or BAICHUAN_DEFAULT_MODEL
    proxy_api_key = model_params.proxy_api_key

    history = []
    messages: List[ModelMessage] = params["messages"]

    # Add history conversation
    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            # As of today, system message is not supported.
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
        else:
            pass

    payload = {
        "model": model_name,
        "messages": history,
        "temperature": params.get("temperature", 0.3),
        "top_k": params.get("top_k", 5),
        "top_p": params.get("top_p", 0.85),
        "stream": True,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + proxy_api_key,
    }

    print(f"Sending request to {url} with model {model_name}")
    res = requests.post(url=url, json=payload, headers=headers)

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
                    if obj["choices"][0]["delta"].get("content") is not None:
                        content = obj["choices"][0]["delta"].get("content")
                        text += content
                yield text


def main():
    model_params = ProxyModelParameters(
        model_name="not-used",
        model_path="not-used",
        proxy_server_url="not-used",
        proxy_api_key="YOUR_BAICHUAN_API_KEY",
        proxyllm_backend="Baichuan2-Turbo-192k",
    )
    final_text = ""
    for part in baichuan_generate_stream(
        model=ProxyModel(model_params=model_params),
        params={
            "messages": [
                ModelMessage(role=ModelMessageRoleType.HUMAN, content="背诵《论语》第一章")
            ]
        },
    ):
        final_text = part
    print(final_text)


if __name__ == "__main__":
    main()
