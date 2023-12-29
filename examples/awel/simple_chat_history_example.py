"""AWEL: Simple chat with history example

    DB-GPT will automatically load and execute the current file after startup.

    Examples:

        Call with non-streaming response.
        .. code-block:: shell

            DBGPT_SERVER="http://127.0.0.1:5000"
            MODEL="gpt-3.5-turbo"
            # Fist round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "gpt-3.5-turbo",
                "context": {
                    "conv_uid": "uuid_conv_1234"
                },
                "messages": "Who is elon musk?"
            }'

            # Second round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "gpt-3.5-turbo",
                "context": {
                    "conv_uid": "uuid_conv_1234"
                },
                "messages": "Is he rich?"
            }'

        Call with streaming response.
        .. code-block:: shell

            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "gpt-3.5-turbo",
                "context": {
                    "conv_uid": "uuid_conv_stream_1234"
                },
                "stream": true,
                "messages": "Who is elon musk?"
            }'

            # Second round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_history/multi_round/chat/completions \
            -H "Content-Type: application/json" -d '{
                "model": "gpt-3.5-turbo",
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
from dbgpt.core import InMemoryStorage, LLMClient
from dbgpt.core.awel import DAG, HttpTrigger, JoinOperator, MapOperator
from dbgpt.core.operator import (
    BufferedConversationMapperOperator,
    LLMBranchOperator,
    LLMOperator,
    PostConversationOperator,
    PostStreamingConversationOperator,
    PreConversationOperator,
    RequestBuildOperator,
    StreamingLLMOperator,
)
from dbgpt.model import MixinLLMOperator, OpenAIStreamingOperator

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


class MyLLMOperator(MixinLLMOperator, LLMOperator):
    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client)
        LLMOperator.__init__(self, llm_client, **kwargs)


class MyStreamingLLMOperator(MixinLLMOperator, StreamingLLMOperator):
    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client)
        StreamingLLMOperator.__init__(self, llm_client, **kwargs)


with DAG("dbgpt_awel_simple_chat_history") as multi_round_dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_history/multi_round/chat/completions",
        methods="POST",
        request_body=TriggerReqBody,
        streaming_predict_func=lambda req: req.stream,
    )
    # Transform request body to model request.
    request_handle_task = RequestBuildOperator()
    # Pre-process conversation, use InMemoryStorage to store conversation.
    pre_conversation_task = PreConversationOperator(
        storage=InMemoryStorage(), message_storage=InMemoryStorage()
    )
    # Keep last k round conversation.
    history_conversation_task = BufferedConversationMapperOperator(last_k_round=5)

    # Save conversation to storage.
    post_conversation_task = PostConversationOperator()
    # Save streaming conversation to storage.
    post_streaming_conversation_task = PostStreamingConversationOperator()

    # Use LLMOperator to generate response.
    llm_task = MyLLMOperator(task_name="llm_task")
    streaming_llm_task = MyStreamingLLMOperator(task_name="streaming_llm_task")
    branch_task = LLMBranchOperator(
        stream_task_name="streaming_llm_task", no_stream_task_name="llm_task"
    )
    model_parse_task = MapOperator(lambda out: out.to_dict())
    openai_format_stream_task = OpenAIStreamingOperator()
    result_join_task = JoinOperator(
        combine_function=lambda not_stream_out, stream_out: not_stream_out or stream_out
    )

    (
        trigger
        >> request_handle_task
        >> pre_conversation_task
        >> history_conversation_task
        >> branch_task
    )

    # The branch of no streaming response.
    (
        branch_task
        >> llm_task
        >> post_conversation_task
        >> model_parse_task
        >> result_join_task
    )
    # The branch of streaming response.
    (
        branch_task
        >> streaming_llm_task
        >> post_streaming_conversation_task
        >> openai_format_stream_task
        >> result_join_task
    )

if __name__ == "__main__":
    if multi_round_dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([multi_round_dag], port=5555)
    else:
        # Production mode, DB-GPT will automatically load and execute the current file after startup.
        pass
