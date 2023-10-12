import os
import logging
from typing import List
from pilot.model.proxy.llms.proxy_model import ProxyModel
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType

logger = logging.getLogger(__name__)

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
    
    history = []

    messages: List[ModelMessage] = params["messages"]
    # Add history conversation

    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "system", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "system", "content": message.content})
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
    
    print(history)  
    gen = Generation()
    res = gen.call(
        proxyllm_backend,
        messages=history,
        top_p=params.get("top_p", 0.8),
        stream=True,
        result_format='message' 
    )
    
    for r in res:
        if r["output"]["choices"][0]["message"].get("content") is not None:
            content = r["output"]["choices"][0]["message"].get("content") 
            yield content 
    
