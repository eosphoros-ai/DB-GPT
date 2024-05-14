"""AWEL: Simple rag rewrite example

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
        python examples/awel/simple_rag_rewrite_example.py
    Example:

    .. code-block:: shell

        DBGPT_SERVER="http://127.0.0.1:5555"
        curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/rag/rewrite \
        -H "Content-Type: application/json" -d '{
            "query": "compare curry and james",
            "context":"steve curry and lebron james are nba all-stars"
        }'
"""
from typing import Dict

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.rag.operators import QueryRewriteOperator


class TriggerReqBody(BaseModel):
    query: str = Field(..., description="User query")
    context: str = Field(..., description="context")


class RequestHandleOperator(MapOperator[TriggerReqBody, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict:
        params = {
            "query": input_value.query,
            "context": input_value.context,
        }
        print(f"Receive input value: {input_value}")
        return params


with DAG("dbgpt_awel_simple_rag_rewrite_example") as dag:
    trigger = HttpTrigger(
        "/examples/rag/rewrite", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    # build query rewrite operator
    rewrite_task = QueryRewriteOperator(llm_client=OpenAILLMClient(), nums=2)
    trigger >> request_handle_task >> rewrite_task


if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass
