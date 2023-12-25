from abc import ABC
from typing import Optional, Dict, List, Any, Union, AsyncIterator

from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.core.awel import MapOperator

from dbgpt.core.interface.llm import ModelRequest


class GptsRequestBuildOperator(MapOperator[Union[Dict, str], ModelRequest], ABC):
    def __init__(self, model: str = None, **kwargs):
        self._model = model
        super().__init__(**kwargs)

    async def map(self, input_value: Union[Dict, str]) -> ModelRequest:
        if isinstance(input_value, str):
            return ModelRequest._build(self._model, input_value)
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
            raise ValueError("Requset input Error!")
