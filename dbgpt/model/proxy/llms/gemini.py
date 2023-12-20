from typing import List

from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType

GEMINI_DEFAULT_MODEL = "gemini-pro"

# global history for the easy to support history
# TODO refactor the history thing in the future
history = []


def gemini_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://open.bigmodel.cn/dev/api#overview"""
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")
    global history

    # TODO proxy model use unified config?
    proxy_api_key = model_params.proxy_api_key
    proxyllm_backend = GEMINI_DEFAULT_MODEL or model_params.proxyllm_backend

    generation_config = {
        "temperature": 0.7,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
    ]

    import google.generativeai as genai

    if model_params.proxy_api_base:
        from google.api_core import client_options

        client_opts = client_options.ClientOptions(
            api_endpoint=model_params.proxy_api_base
        )
        genai.configure(
            api_key=proxy_api_key, transport="rest", client_options=client_opts
        )
    else:
        genai.configure(api_key=proxy_api_key)
    model = genai.GenerativeModel(
        model_name=proxyllm_backend,
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    messages = params["messages"][0].content
    chat = model.start_chat(history=history)
    response = chat.send_message(messages, stream=True)
    text = ""
    for chunk in response:
        text += chunk.text
        yield text
    # only keep the last five message
    if len(history) > 10:
        history = chat.history[2:]
    else:
        history = chat.history
