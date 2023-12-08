import logging
from typing import List
from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType

logger = logging.getLogger(__name__)


def __convert_2_tongyi_messages(messages: List[ModelMessage]):
    chat_round = 0
    tongyi_messages = []

    last_usr_message = ""
    system_messages = []

    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            last_usr_message = message.content
        elif message.role == ModelMessageRoleType.SYSTEM:
            system_messages.append(message.content)
        elif message.role == ModelMessageRoleType.AI:
            last_ai_message = message.content
            tongyi_messages.append({"role": "user", "content": last_usr_message})
            tongyi_messages.append({"role": "assistant", "content": last_ai_message})
    if len(system_messages) > 0:
        if len(system_messages) < 2:
            tongyi_messages.insert(0, {"role": "system", "content": system_messages[0]})
        else:
            tongyi_messages.append({"role": "user", "content": system_messages[1]})
    else:
        last_message = messages[-1]
        if last_message.role == ModelMessageRoleType.HUMAN:
            tongyi_messages.append({"role": "user", "content": last_message.content})

    return tongyi_messages


def tongyi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    import dashscope
    from dashscope import Generation

    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    proxy_api_key = model_params.proxy_api_key
    dashscope.api_key = proxy_api_key

    proxyllm_backend = model_params.proxyllm_backend
    if not proxyllm_backend:
        proxyllm_backend = Generation.Models.qwen_turbo  # By Default qwen_turbo

    messages: List[ModelMessage] = params["messages"]

    history = __convert_2_tongyi_messages(messages)
    gen = Generation()
    res = gen.call(
        proxyllm_backend,
        messages=history,
        top_p=params.get("top_p", 0.8),
        stream=True,
        result_format="message",
    )

    for r in res:
        if r:
            if r["status_code"] == 200:
                content = r["output"]["choices"][0]["message"].get("content")
                yield content
            else:
                content = r["code"] + ":" + r["message"]
                yield content
