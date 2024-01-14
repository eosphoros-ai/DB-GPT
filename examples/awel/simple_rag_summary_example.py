"""AWEL:
This example shows how to use AWEL to build a simple rag summary example.
    pre-requirements:
        1. install openai python sdk
        ```
            pip install openai
        ```
        2. set openai key and base
        ```
            export OPENAI_API_KEY={your_openai_key}
            export OPENAI_API_BASE={your_openai_base}
        ```
        or
        ```
            import os
            os.environ["OPENAI_API_KEY"] = {your_openai_key}
            os.environ["OPENAI_API_BASE"] = {your_openai_base}
        ```
        python examples/awel/simple_rag_summary_example.py
    Example:

    .. code-block:: shell

        DBGPT_SERVER="http://127.0.0.1:5000"
        FILE_PATH="{your_file_path}"
        curl -X POST http://127.0.0.1:5555/api/v1/awel/trigger/examples/rag/summary \
        -H "Content-Type: application/json" -d '{
            "file_path": $FILE_PATH
        }'
"""
from typing import Dict

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.model import OpenAILLMClient
from dbgpt.rag.operator.knowledge import KnowledgeOperator
from dbgpt.rag.operator.summary import SummaryAssemblerOperator


class TriggerReqBody(BaseModel):
    file_path: str = Field(..., description="file_path")


class RequestHandleOperator(MapOperator[TriggerReqBody, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict:
        params = {
            "file_path": input_value.file_path,
        }
        print(f"Receive input value: {input_value}")
        return params


with DAG("dbgpt_awel_simple_rag_rewrite_example") as dag:
    trigger = HttpTrigger(
        "/examples/rag/summary", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    path_operator = MapOperator(lambda request: request["file_path"])
    # build knowledge operator
    knowledge_operator = KnowledgeOperator()
    # build summary assembler operator
    summary_operator = SummaryAssemblerOperator(
        llm_client=OpenAILLMClient(), language="en"
    )
    (
        trigger
        >> request_handle_task
        >> path_operator
        >> knowledge_operator
        >> summary_operator
    )


if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass
