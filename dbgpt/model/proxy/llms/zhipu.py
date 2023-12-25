from typing import List

from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType

CHATGLM_DEFAULT_MODEL = "chatglm_pro"


def __convert_2_zhipu_messages(messages: List[ModelMessage]):
    chat_round = 0
    wenxin_messages = []

    last_usr_message = ""
    system_messages = []

    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            last_usr_message = message.content
        elif message.role == ModelMessageRoleType.SYSTEM:
            system_messages.append(message.content)
        elif message.role == ModelMessageRoleType.AI:
            last_ai_message = message.content
            wenxin_messages.append({"role": "user", "content": last_usr_message})
            wenxin_messages.append({"role": "assistant", "content": last_ai_message})

    # build last user messge

    if len(system_messages) > 0:
        if len(system_messages) > 1:
            end_message = system_messages[-1]
        else:
            last_message = messages[-1]
            if last_message.role == ModelMessageRoleType.HUMAN:
                end_message = system_messages[-1] + "\n" + last_message.content
            else:
                end_message = system_messages[-1]
    else:
        last_message = messages[-1]
        end_message = last_message.content
    wenxin_messages.append({"role": "user", "content": end_message})
    return wenxin_messages, system_messages


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

    messages: List[ModelMessage] = params["messages"]
    history, systems = __convert_2_zhipu_messages(messages)
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
