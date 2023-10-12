import os
import json
from typing import List

from pilot.model.proxy.llms.proxy_model import ProxyModel
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType

CHATGLM_DEFAULT_MODEL = "chatglm_pro"

def zhipu_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://open.bigmodel.cn/dev/api#overview"""
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    # TODO proxy model use unified config?
    proxy_api_key = model_params.proxy_api_key
    proxyllm_backend = CHATGLM_DEFAULT_MODEL or model_params.proxyllm_backend 

    import zhipuai
    zhipuai.api_key = proxy_api_key

    history = []

    messages: List[ModelMessage] = params["messages"]
    # Add history conversation

    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "system", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
        else:
            pass

    res = zhipuai.model_api.sse_invoke(
        model=proxyllm_backend,
        prompt=history,
        temperature=params.get("temperature"),
        top_p=params.get("top_p"),
        incremental=False,
    )
    for r in res.events():
        if r.event == "add":
            yield r.data