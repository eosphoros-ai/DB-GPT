"""AWEL: Simple dag example

    DB-GPT will automatically load and execute the current file after startup.

    Example:

    .. code-block:: shell

        DBGPT_SERVER="http://127.0.0.1:5555"
        curl -X GET $DBGPT_SERVER/api/v1/awel/trigger/examples/hello\?name\=zhangsan

"""
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator


class TriggerReqBody(BaseModel):
    name: str = Field(..., description="User name")
    age: int = Field(18, description="User age")


class RequestHandleOperator(MapOperator[TriggerReqBody, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> str:
        print(f"Receive input value: {input_value}")
        return f"Hello, {input_value.name}, your age is {input_value.age}"


with DAG("simple_dag_example") as dag:
    trigger = HttpTrigger("/examples/hello", request_body=TriggerReqBody)
    map_node = RequestHandleOperator()
    trigger >> map_node

if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag])
    else:
        pass
