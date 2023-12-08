"""AWEL: Simple chat dag example

    DB-GPT will automatically load and execute the current file after startup.

    Example:

    .. code-block:: shell

        curl -X POST http://127.0.0.1:5000/api/v1/awel/trigger/examples/simple_chat \
        -H "Content-Type: application/json" -d '{
            "model": "proxyllm",
            "user_input": "hello"
        }'
"""
from typing import Dict
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.core import ModelMessage
from dbgpt.model.operator.model_operator import ModelOperator


class TriggerReqBody(BaseModel):
    model: str = Field(..., description="Model name")
    user_input: str = Field(..., description="User input")


class RequestHandleOperator(MapOperator[TriggerReqBody, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict:
        hist = []
        hist.append(ModelMessage.build_human_message(input_value.user_input))
        hist = list(h.dict() for h in hist)
        params = {
            "prompt": input_value.user_input,
            "messages": hist,
            "model": input_value.model,
            "echo": False,
        }
        print(f"Receive input value: {input_value}")
        return params


with DAG("dbgpt_awel_simple_dag_example") as dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_chat", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    model_task = ModelOperator()
    # type(out) == ModelOutput
    model_parse_task = MapOperator(lambda out: out.to_dict())
    trigger >> request_handle_task >> model_task >> model_parse_task
