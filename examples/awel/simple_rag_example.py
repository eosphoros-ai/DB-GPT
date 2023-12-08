"""AWEL: Simple rag example

    DB-GPT will automatically load and execute the current file after startup.

    Example:

    .. code-block:: shell

        curl -X POST http://127.0.0.1:5000/api/v1/awel/trigger/examples/simple_rag \
        -H "Content-Type: application/json" -d '{
            "conv_uid": "36f0e992-8825-11ee-8638-0242ac150003",
            "model_name": "proxyllm",
            "chat_mode": "chat_knowledge",
            "user_input": "What is DB-GPT?",
            "select_param": "default"
        }'

"""

from dbgpt.core.awel import HttpTrigger, DAG, MapOperator
from dbgpt.app.scene.operator._experimental import (
    ChatContext,
    PromptManagerOperator,
    ChatHistoryStorageOperator,
    ChatHistoryOperator,
    EmbeddingEngingOperator,
    BaseChatOperator,
)
from dbgpt.app.scene import ChatScene
from dbgpt.app.openapi.api_view_model import ConversationVo
from dbgpt.model.operator.model_operator import ModelOperator


class RequestParseOperator(MapOperator[ConversationVo, ChatContext]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: ConversationVo) -> ChatContext:
        return ChatContext(
            current_user_input=input_value.user_input,
            model_name=input_value.model_name,
            chat_session_id=input_value.conv_uid,
            select_param=input_value.select_param,
            chat_scene=ChatScene.ChatKnowledge,
        )


with DAG("simple_rag_example") as dag:
    trigger_task = HttpTrigger(
        "/examples/simple_rag", methods="POST", request_body=ConversationVo
    )
    req_parse_task = RequestParseOperator()
    # TODO should register prompt template first
    prompt_task = PromptManagerOperator()
    history_storage_task = ChatHistoryStorageOperator()
    history_task = ChatHistoryOperator()
    embedding_task = EmbeddingEngingOperator()
    chat_task = BaseChatOperator()
    model_task = ModelOperator()
    output_parser_task = MapOperator(lambda out: out.to_dict()["text"])

    (
        trigger_task
        >> req_parse_task
        >> prompt_task
        >> history_storage_task
        >> history_task
        >> embedding_task
        >> chat_task
        >> model_task
        >> output_parser_task
    )
