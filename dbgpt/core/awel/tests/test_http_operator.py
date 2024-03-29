from typing import List

import pytest

from .. import (
    DAG,
    BranchOperator,
    DAGContext,
    InputOperator,
    JoinOperator,
    MapOperator,
    ReduceStreamOperator,
    SimpleInputSource,
    TaskState,
    WorkflowRunner,
)
from .conftest import (
    _is_async_iterator,
    input_node,
    input_nodes,
    runner,
    stream_input_node,
    stream_input_nodes,
)


def _register_dag_to_fastapi_app(dag):
    # TODO
    pass


@pytest.mark.asyncio
async def test_http_operator(runner: WorkflowRunner, stream_input_node: InputOperator):
    with DAG("test_map") as dag:
        pass
        # http_req_task = HttpRequestOperator(endpoint="/api/completions")
        # db_task = DBQueryOperator(table_name="user_info")
        # prompt_task = PromptTemplateOperator(
        #     system_prompt="You are an AI designed to solve the user's goals with given commands, please follow the  constraints of the system's input for your answers."
        # )
        # llm_task = ChatGPTLLMOperator(model="chagpt-3.5")
        # output_parser_task = CommonOutputParserOperator()
        # http_res_task = HttpResponseOperator()
        # (
        #     http_req_task
        #     >> db_task
        #     >> prompt_task
        #     >> llm_task
        #     >> output_parser_task
        #     >> http_res_task
        # )

    _register_dag_to_fastapi_app(dag)
