from typing import Dict, Optional, Union

from dbgpt.core.interface.llm import ModelRequest


def _build_model_request(
    input_value: Union[Dict, str], model: Optional[str] = None
) -> ModelRequest:
    """Build model request from input value.

    Args:
        input_value(str or dict): input value
        model(Optional[str]): model name

    Returns:
        ModelRequest: model request, pass to llm client
    """
    if isinstance(input_value, str):
        return ModelRequest._build(model, input_value)
    elif isinstance(input_value, dict):
        parm = {
            "model": input_value.get("model"),
            "messages": input_value.get("messages"),
            "temperature": input_value.get("temperature", None),
            "max_new_tokens": input_value.get("max_new_tokens", None),
            "stop": input_value.get("stop", None),
            "stop_token_ids": input_value.get("stop_token_ids", None),
            "context_len": input_value.get("context_len", None),
            "echo": input_value.get("echo", None),
            "span_id": input_value.get("span_id", None),
        }

        return ModelRequest(**parm)
    else:
        raise ValueError("Build model request input Error!")
