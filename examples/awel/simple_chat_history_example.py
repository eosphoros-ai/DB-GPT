"""AWEL: Simple chat with history example

    DB-GPT will automatically load and execute the current file after startup.

    Examples:

        Call with non-streaming response.
        .. code-block:: shell

            DBGPT_SERVER="http://127.0.0.1:5555"
            MODEL="gpt-3.5-turbo"
            # Fist round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "'"$MODEL"'",
                "context": {
                    "conv_uid": "uuid_conv_1234"
                },
                "messages": "Who is elon musk?"
            }'

            # Second round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "'"$MODEL"'",
                "context": {
                    "conv_uid": "uuid_conv_1234"
                },
                "messages": "Is he rich?"
            }'

        Call with streaming response.
        .. code-block:: shell

            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "'"$MODEL"'",
                "context": {
                    "conv_uid": "uuid_conv_stream_1234"
                },
                "stream": true,
                "messages": "Who is elon musk?"
            }'

            # Second round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "'"$MODEL"'",
                "context": {
                    "conv_uid": "uuid_conv_stream_1234"
                },
                "stream": true,
                "messages": "Is he rich?"
            }'


"""
import logging
from typing import Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    InMemoryStorage,
    MessagesPlaceholder,
    ModelMessage,
    ModelRequest,
    ModelRequestContext,
    SystemPromptTemplate,
)
from dbgpt.core.awel import DAG, HttpTrigger, JoinOperator, MapOperator
from dbgpt.core.operator import (
    ChatComposerInput,
    ChatHistoryPromptComposerOperator,
    LLMBranchOperator,
)
from dbgpt.model.operator import (
    LLMOperator,
    OpenAIStreamingOutputOperator,
    StreamingLLMOperator,
)

logger = logging.getLogger(__name__)


class ReqContext(BaseModel):
    user_name: Optional[str] = Field(
        None, description="The user name of the model request."
    )

    sys_code: Optional[str] = Field(
        None, description="The system code of the model request."
    )
    conv_uid: Optional[str] = Field(
        None, description="The conversation uid of the model request."
    )


class TriggerReqBody(BaseModel):
    messages: Union[str, List[Dict[str, str]]] = Field(
        ..., description="User input messages"
    )
    model: str = Field(..., description="Model name")
    stream: Optional[bool] = Field(default=False, description="Whether return stream")
    context: Optional[ReqContext] = Field(
        default=None, description="The context of the model request."
    )


async def build_model_request(
    messages: List[ModelMessage], req_body: TriggerReqBody
) -> ModelRequest:
    return ModelRequest.build_request(
        model=req_body.model,
        messages=messages,
        context=req_body.context,
        stream=req_body.stream,
    )


with DAG("dbgpt_awel_simple_chat_history") as multi_round_dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_history/multi_round/chat/completions",
        methods="POST",
        request_body=TriggerReqBody,
        streaming_predict_func=lambda req: req.stream,
    )
    prompt = ChatPromptTemplate(
        messages=[
            SystemPromptTemplate.from_template("You are a helpful chatbot."),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanPromptTemplate.from_template("{user_input}"),
        ]
    )

    composer_operator = ChatHistoryPromptComposerOperator(
        prompt_template=prompt,
        keep_end_rounds=5,
        storage=InMemoryStorage(),
        message_storage=InMemoryStorage(),
    )

    # Use BaseLLMOperator to generate response.
    llm_task = LLMOperator(task_name="llm_task")
    streaming_llm_task = StreamingLLMOperator(task_name="streaming_llm_task")
    branch_task = LLMBranchOperator(
        stream_task_name="streaming_llm_task", no_stream_task_name="llm_task"
    )
    model_parse_task = MapOperator(lambda out: out.to_dict())
    openai_format_stream_task = OpenAIStreamingOutputOperator()
    result_join_task = JoinOperator(
        combine_function=lambda not_stream_out, stream_out: not_stream_out or stream_out
    )

    req_handle_task = MapOperator(
        lambda req: ChatComposerInput(
            context=ModelRequestContext(
                conv_uid=req.context.conv_uid, stream=req.stream
            ),
            prompt_dict={"user_input": req.messages},
            model_dict={
                "model": req.model,
                "context": req.context,
                "stream": req.stream,
            },
        )
    )

    trigger >> req_handle_task >> composer_operator >> branch_task

    # The branch of no streaming response.
    branch_task >> llm_task >> model_parse_task >> result_join_task
    # The branch of streaming response.
    branch_task >> streaming_llm_task >> openai_format_stream_task >> result_join_task

if __name__ == "__main__":
    if multi_round_dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([multi_round_dag], port=5555)
    else:
        # Production mode, DB-GPT will automatically load and execute the current file after startup.
        pass
