from typing import List, Tuple, Dict, Any

from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.core.interface.message import ModelMessage, parse_model_messages

GEMINI_DEFAULT_MODEL = "gemini-pro"


def gemini_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://open.bigmodel.cn/dev/api#overview"""
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

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
    messages: List[ModelMessage] = params["messages"]
    user_prompt, gemini_hist = _transform_to_gemini_messages(messages)
    chat = model.start_chat(history=gemini_hist)
    response = chat.send_message(user_prompt, stream=True)
    text = ""
    for chunk in response:
        text += chunk.text
        print(text)
        yield text


def _transform_to_gemini_messages(
    messages: List[ModelMessage],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Transform messages to gemini format

    See https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_python.ipynb

    Args:
        messages (List[ModelMessage]): messages

    Returns:
        Tuple[str, List[Dict[str, Any]]]: user_prompt, gemini_hist

    Examples:
        .. code-block:: python

            messages = [
                ModelMessage(role="human", content="Hello"),
                ModelMessage(role="ai", content="Hi there!"),
                ModelMessage(role="human", content="How are you?"),
            ]
            user_prompt, gemini_hist = _transform_to_gemini_messages(messages)
            assert user_prompt == "How are you?"
            assert gemini_hist == [
                {"role": "user", "parts": {"text": "Hello"}},
                {"role": "model", "parts": {"text": "Hi there!"}},
            ]
    """
    user_prompt, system_messages, history_messages = parse_model_messages(messages)
    if system_messages:
        user_prompt = "".join(system_messages) + "\n" + user_prompt
    gemini_hist = []
    if history_messages:
        for user_message, model_message in history_messages:
            gemini_hist.append({"role": "user", "parts": {"text": user_message}})
            gemini_hist.append({"role": "model", "parts": {"text": model_message}})
    return user_prompt, gemini_hist
