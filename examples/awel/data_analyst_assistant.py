"""AWEL: Data analyst assistant.

    DB-GPT will automatically load and execute the current file after startup.

    Examples:

        .. code-block:: shell

            # Run this file in your terminal with dev mode.
            # First terminal
            export OPENAI_API_KEY=xxx
            export OPENAI_API_BASE=https://api.openai.com/v1
            python examples/awel/simple_chat_history_example.py


        Code fix command, return no streaming response

        .. code-block:: shell

            # Open a new terminal
            # Second terminal

            DBGPT_SERVER="http://127.0.0.1:5555"
            MODEL="gpt-3.5-turbo"
            # Fist round
            curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/data_analyst/copilot \
            -H "Content-Type: application/json" -d '{
                "command": "dbgpt_awel_data_analyst_code_fix",
                "model": "gpt-3.5-turbo",
                "stream": false,
                "context": {
                    "conv_uid": "uuid_conv_copilot_1234",
                    "chat_mode": "chat_with_code"
                },
                "messages": "SELECT * FRM orders WHERE order_amount > 500;"
            }'

"""
import logging
from functools import cache
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import (
    InMemoryStorage,
    LLMClient,
    MessageStorageItem,
    ModelMessage,
    ModelMessageRoleType,
    PromptManager,
    PromptTemplate,
    StorageConversation,
    StorageInterface,
)
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
from dbgpt.util.utils import colored

logger = logging.getLogger(__name__)

CODE_FIX = "dbgpt_awel_data_analyst_code_fix"
CODE_PERF = "dbgpt_awel_data_analyst_code_perf"
CODE_EXPLAIN = "dbgpt_awel_data_analyst_code_explain"
CODE_COMMENT = "dbgpt_awel_data_analyst_code_comment"
CODE_TRANSLATE = "dbgpt_awel_data_analyst_code_translate"

CODE_FIX_TEMPLATE_ZH = """作为一名经验丰富的数据仓库开发者和数据分析师，
这里有一段 {language} 代码。请按照最佳实践检查代码，找出并修复所有错误。请给出修复后的代码，并且提供对您所做的每一行更正的逐行解释，请使用和用户相同的语言进行回答。"""
CODE_FIX_TEMPLATE_EN = """As an experienced data warehouse developer and data analyst, 
here is a snippet of code of {language}. Please review the code following best practices to identify and fix all errors. 
Provide the corrected code and include a line-by-line explanation of all the fixes you've made, please use the same language as the user."""

CODE_PERF_TEMPLATE_ZH = """作为一名经验丰富的数据仓库开发者和数据分析师，这里有一段 {language} 代码。
请你按照最佳实践来优化这段代码。请在代码中加入注释点明所做的更改，并解释每项优化的原因，以便提高代码的维护性和性能，请使用和用户相同的语言进行回答。"""
CODE_PERF_TEMPLATE_EN = """As an experienced data warehouse developer and data analyst, 
you are provided with a snippet of code of {language}. Please optimize the code according to best practices. 
Include comments to highlight the changes made and explain the reasons for each optimization for better maintenance and performance, 
please use the same language as the user."""
CODE_EXPLAIN_TEMPLATE_ZH = """作为一名经验丰富的数据仓库开发者和数据分析师，
现在给你的是一份 {language} 代码。请你逐行解释代码的含义，请使用和用户相同的语言进行回答。"""

CODE_EXPLAIN_TEMPLATE_EN = """As an experienced data warehouse developer and data analyst, 
you are provided with a snippet of code of {language}. Please explain the meaning of the code line by line, 
please use the same language as the user."""

CODE_COMMENT_TEMPLATE_ZH = """作为一名经验丰富的数据仓库开发者和数据分析师，现在给你的是一份 {language} 代码。
请你为每一行代码添加注释，解释每个部分的作用，请使用和用户相同的语言进行回答。"""

CODE_COMMENT_TEMPLATE_EN = """As an experienced Data Warehouse Developer and Data Analyst. 
Below is a snippet of code written in {language}. 
Please provide line-by-line comments explaining what each section of the code does, please use the same language as the user."""

CODE_TRANSLATE_TEMPLATE_ZH = """作为一名经验丰富的数据仓库开发者和数据分析师，现在手头有一份用{source_language}语言编写的代码片段。
请你将这段代码准确无误地翻译成{target_language}语言，确保语法和功能在翻译后的代码中得到正确体现，请使用和用户相同的语言进行回答。"""
CODE_TRANSLATE_TEMPLATE_EN = """As an experienced data warehouse developer and data analyst, 
you're presented with a snippet of code written in {source_language}. 
Please translate this code into {target_language} ensuring that the syntax and functionalities are accurately reflected in the translated code, 
please use the same language as the user."""


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
    chat_mode: Optional[str] = Field(
        "chat_with_code", description="The chat mode of the model request."
    )


class TriggerReqBody(BaseModel):
    messages: str = Field(..., description="User input messages")
    command: Optional[str] = Field(default="fix", description="Command name")
    model: Optional[str] = Field(default="gpt-3.5-turbo", description="Model name")
    stream: Optional[bool] = Field(default=False, description="Whether return stream")
    language: Optional[str] = Field(default="hive", description="Language")
    target_language: Optional[str] = Field(
        default="hive", description="Target language, use in translate"
    )
    context: Optional[ReqContext] = Field(
        default=None, description="The context of the model request."
    )


@cache
def load_or_save_prompt_template(pm: PromptManager):
    ext_params = {
        "chat_scene": "chat_with_code",
        "sub_chat_scene": "data_analyst",
        "prompt_type": "common",
    }
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_FIX_TEMPLATE_ZH,
        ),
        prompt_name=CODE_FIX,
        prompt_language="zh",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_FIX_TEMPLATE_EN,
        ),
        prompt_name=CODE_FIX,
        prompt_language="en",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_PERF_TEMPLATE_ZH,
        ),
        prompt_name=CODE_PERF,
        prompt_language="zh",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_PERF_TEMPLATE_EN,
        ),
        prompt_name=CODE_PERF,
        prompt_language="en",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_EXPLAIN_TEMPLATE_ZH,
        ),
        prompt_name=CODE_EXPLAIN,
        prompt_language="zh",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_EXPLAIN_TEMPLATE_EN,
        ),
        prompt_name=CODE_EXPLAIN,
        prompt_language="en",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_COMMENT_TEMPLATE_ZH,
        ),
        prompt_name=CODE_COMMENT,
        prompt_language="zh",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["language"],
            template=CODE_COMMENT_TEMPLATE_EN,
        ),
        prompt_name=CODE_COMMENT,
        prompt_language="en",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["source_language", "target_language"],
            template=CODE_TRANSLATE_TEMPLATE_ZH,
        ),
        prompt_name=CODE_TRANSLATE,
        prompt_language="zh",
        **ext_params,
    )
    pm.query_or_save(
        PromptTemplate(
            input_variables=["source_language", "target_language"],
            template=CODE_TRANSLATE_TEMPLATE_EN,
        ),
        prompt_name=CODE_TRANSLATE,
        prompt_language="en",
        **ext_params,
    )


class CopilotOperator(MapOperator[TriggerReqBody, Dict[str, Any]]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._default_prompt_manager = PromptManager()

    async def map(self, input_value: TriggerReqBody) -> Dict[str, Any]:
        from dbgpt.serve.prompt.serve import SERVE_APP_NAME as PROMPT_SERVE_APP_NAME
        from dbgpt.serve.prompt.serve import Serve as PromptServe

        prompt_serve = self.system_app.get_component(
            PROMPT_SERVE_APP_NAME, PromptServe, default_component=None
        )
        if prompt_serve:
            pm = prompt_serve.prompt_manager
        else:
            pm = self._default_prompt_manager
        load_or_save_prompt_template(pm)

        user_language = self.system_app.config.get_current_lang(default="en")

        prompt_list = pm.prefer_query(
            input_value.command, prefer_prompt_language=user_language
        )
        if not prompt_list:
            error_msg = f"Prompt not found for command {input_value.command}, user_language: {user_language}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        prompt = prompt_list[0].to_prompt_template()
        if input_value.command == CODE_TRANSLATE:
            format_params = {
                "source_language": input_value.language,
                "target_language": input_value.target_language,
            }
        else:
            format_params = {"language": input_value.language}

        system_message = prompt.format(**format_params)
        messages = [
            ModelMessage(role=ModelMessageRoleType.SYSTEM, content=system_message),
            ModelMessage(role=ModelMessageRoleType.HUMAN, content=input_value.messages),
        ]
        context = input_value.context.dict() if input_value.context else {}
        return {
            "messages": messages,
            "stream": input_value.stream,
            "model": input_value.model,
            "context": context,
        }


class MyConversationOperator(PreConversationOperator):
    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs,
    ):
        super().__init__(storage, message_storage, **kwargs)

    def _get_conversion_serve(self):
        from dbgpt.serve.conversation.serve import (
            SERVE_APP_NAME as CONVERSATION_SERVE_APP_NAME,
        )
        from dbgpt.serve.conversation.serve import Serve as ConversationServe

        conversation_serve: ConversationServe = self.system_app.get_component(
            CONVERSATION_SERVE_APP_NAME, ConversationServe, default_component=None
        )
        return conversation_serve

    @property
    def storage(self):
        if self._storage:
            return self._storage
        conversation_serve = self._get_conversion_serve()
        if conversation_serve:
            return conversation_serve.conv_storage
        else:
            logger.info("Conversation storage not found, use InMemoryStorage default")
            self._storage = InMemoryStorage()
            return self._storage

    @property
    def message_storage(self):
        if self._message_storage:
            return self._message_storage
        conversation_serve = self._get_conversion_serve()
        if conversation_serve:
            return conversation_serve.message_storage
        else:
            logger.info("Message storage not found, use InMemoryStorage default")
            self._message_storage = InMemoryStorage()
            return self._message_storage


class MyLLMOperator(MixinLLMOperator, LLMOperator):
    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client)
        LLMOperator.__init__(self, llm_client, **kwargs)


class MyStreamingLLMOperator(MixinLLMOperator, StreamingLLMOperator):
    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client)
        StreamingLLMOperator.__init__(self, llm_client, **kwargs)


def history_message_mapper(
    messages_by_round: List[List[ModelMessage]],
) -> List[ModelMessage]:
    """Mapper for history conversation.

    If there are multi system messages, just keep the first system message.
    """
    has_system_message = False
    mapper_messages = []
    for messages in messages_by_round:
        for message in messages:
            if message.role == ModelMessageRoleType.SYSTEM:
                if has_system_message:
                    continue
                else:
                    mapper_messages.append(message)
                    has_system_message = True
            else:
                mapper_messages.append(message)
    print("history_message_mapper start:" + "=" * 70)
    print(colored(ModelMessage.get_printable_message(mapper_messages), "green"))
    print("history_message_mapper end:" + "=" * 72)
    return mapper_messages


with DAG("dbgpt_awel_data_analyst_assistant") as dag:
    trigger = HttpTrigger(
        "/examples/data_analyst/copilot",
        request_body=TriggerReqBody,
        methods="POST",
        streaming_predict_func=lambda x: x.stream,
    )

    copilot_task = CopilotOperator()
    request_handle_task = RequestBuildOperator()

    # Pre-process conversation
    pre_conversation_task = MyConversationOperator()
    # Keep last k round conversation.
    history_conversation_task = BufferedConversationMapperOperator(
        last_k_round=5, message_mapper=history_message_mapper
    )

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
        >> copilot_task
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
    if dag.leaf_nodes[0].dev_mode:
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag])
    else:
        pass
