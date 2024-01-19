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
                "model": "'"$MODEL"'",
                "stream": false,
                "context": {
                    "conv_uid": "uuid_conv_copilot_1234",
                    "chat_mode": "chat_with_code"
                },
                "messages": "SELECT * FRM orders WHERE order_amount > 500;"
            }'

"""
import logging
import os
from functools import cache
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    ModelMessage,
    ModelRequest,
    ModelRequestContext,
    PromptManager,
    PromptTemplate,
    SystemPromptTemplate,
)
from dbgpt.core.awel import DAG, HttpTrigger, JoinOperator, MapOperator
from dbgpt.core.operator import (
    BufferedConversationMapperOperator,
    HistoryDynamicPromptBuilderOperator,
    LLMBranchOperator,
    RequestBuilderOperator,
)
from dbgpt.model.operator import (
    LLMOperator,
    OpenAIStreamingOutputOperator,
    StreamingLLMOperator,
)
from dbgpt.serve.conversation.operator import ServePreChatHistoryLoadOperator

logger = logging.getLogger(__name__)

PROMPT_LANG_ZH = "zh"
PROMPT_LANG_EN = "en"

CODE_DEFAULT = "dbgpt_awel_data_analyst_code_default"
CODE_FIX = "dbgpt_awel_data_analyst_code_fix"
CODE_PERF = "dbgpt_awel_data_analyst_code_perf"
CODE_EXPLAIN = "dbgpt_awel_data_analyst_code_explain"
CODE_COMMENT = "dbgpt_awel_data_analyst_code_comment"
CODE_TRANSLATE = "dbgpt_awel_data_analyst_code_translate"

CODE_DEFAULT_TEMPLATE_ZH = """作为一名经验丰富的数据仓库开发者和数据分析师。
你可以根据最佳实践来优化代码, 也可以对代码进行修复, 解释, 添加注释, 以及将代码翻译成其他语言。"""
CODE_DEFAULT_TEMPLATE_EN = """As an experienced data warehouse developer and data analyst.
You can optimize the code according to best practices, or fix, explain, add comments to the code, 
and you can also translate the code into other languages.
"""

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
    command: Optional[str] = Field(
        default=None, description="Command name, None if common chat"
    )
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
    zh_ext_params = {
        "chat_scene": "chat_with_code",
        "sub_chat_scene": "data_analyst",
        "prompt_type": "common",
        "prompt_language": PROMPT_LANG_ZH,
    }
    en_ext_params = {
        "chat_scene": "chat_with_code",
        "sub_chat_scene": "data_analyst",
        "prompt_type": "common",
        "prompt_language": PROMPT_LANG_EN,
    }

    pm.query_or_save(
        PromptTemplate.from_template(CODE_DEFAULT_TEMPLATE_ZH),
        prompt_name=CODE_DEFAULT,
        **zh_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_DEFAULT_TEMPLATE_EN),
        prompt_name=CODE_DEFAULT,
        **en_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_FIX_TEMPLATE_ZH),
        prompt_name=CODE_FIX,
        **zh_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_FIX_TEMPLATE_EN),
        prompt_name=CODE_FIX,
        **en_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_PERF_TEMPLATE_ZH),
        prompt_name=CODE_PERF,
        **zh_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_PERF_TEMPLATE_EN),
        prompt_name=CODE_PERF,
        **en_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_EXPLAIN_TEMPLATE_ZH),
        prompt_name=CODE_EXPLAIN,
        **zh_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_EXPLAIN_TEMPLATE_EN),
        prompt_name=CODE_EXPLAIN,
        **en_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_COMMENT_TEMPLATE_ZH),
        prompt_name=CODE_COMMENT,
        **zh_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_COMMENT_TEMPLATE_EN),
        prompt_name=CODE_COMMENT,
        **en_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_TRANSLATE_TEMPLATE_ZH),
        prompt_name=CODE_TRANSLATE,
        **zh_ext_params,
    )
    pm.query_or_save(
        PromptTemplate.from_template(CODE_TRANSLATE_TEMPLATE_EN),
        prompt_name=CODE_TRANSLATE,
        **en_ext_params,
    )


class PromptTemplateBuilderOperator(MapOperator[TriggerReqBody, ChatPromptTemplate]):
    """Build prompt template for chat with code."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._default_prompt_manager = PromptManager()

    async def map(self, input_value: TriggerReqBody) -> ChatPromptTemplate:
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
        if not input_value.command:
            # No command, just chat, not include system prompt.
            default_prompt_list = pm.prefer_query(
                CODE_DEFAULT, prefer_prompt_language=user_language
            )
            default_prompt_template = (
                default_prompt_list[0].to_prompt_template().template
            )
            prompt = ChatPromptTemplate(
                messages=[
                    SystemPromptTemplate.from_template(default_prompt_template),
                    MessagesPlaceholder(variable_name="chat_history"),
                    HumanPromptTemplate.from_template("{user_input}"),
                ]
            )
            return prompt

        # Query prompt template from prompt manager by command name
        prompt_list = pm.prefer_query(
            input_value.command, prefer_prompt_language=user_language
        )
        if not prompt_list:
            error_msg = f"Prompt not found for command {input_value.command}, user_language: {user_language}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        prompt_template = prompt_list[0].to_prompt_template()

        return ChatPromptTemplate(
            messages=[
                SystemPromptTemplate.from_template(prompt_template.template),
                MessagesPlaceholder(variable_name="chat_history"),
                HumanPromptTemplate.from_template("{user_input}"),
            ]
        )


def parse_prompt_args(req: TriggerReqBody) -> Dict[str, Any]:
    prompt_args = {"user_input": req.messages}
    if not req.command:
        return prompt_args
    if req.command == CODE_TRANSLATE:
        prompt_args["source_language"] = req.language
        prompt_args["target_language"] = req.target_language
    else:
        prompt_args["language"] = req.language
    return prompt_args


async def build_model_request(
    messages: List[ModelMessage], req_body: TriggerReqBody
) -> ModelRequest:
    return ModelRequest.build_request(
        model=req_body.model,
        messages=messages,
        context=req_body.context,
        stream=req_body.stream,
    )


with DAG("dbgpt_awel_data_analyst_assistant") as dag:
    trigger = HttpTrigger(
        "/examples/data_analyst/copilot",
        request_body=TriggerReqBody,
        methods="POST",
        streaming_predict_func=lambda x: x.stream,
    )

    prompt_template_load_task = PromptTemplateBuilderOperator()
    request_handle_task = RequestBuilderOperator()

    # Load and store chat history
    chat_history_load_task = ServePreChatHistoryLoadOperator()
    keep_start_rounds = int(os.getenv("DBGPT_AWEL_DATA_ANALYST_KEEP_START_ROUNDS", 0))
    keep_end_rounds = int(os.getenv("DBGPT_AWEL_DATA_ANALYST_KEEP_END_ROUNDS", 5))
    # History transform task, here we keep `keep_start_rounds` round messages of history,
    # and keep `keep_end_rounds` round messages of history.
    history_transform_task = BufferedConversationMapperOperator(
        keep_start_rounds=keep_start_rounds, keep_end_rounds=keep_end_rounds
    )
    history_prompt_build_task = HistoryDynamicPromptBuilderOperator(
        history_key="chat_history"
    )

    model_request_build_task = JoinOperator(build_model_request)

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
    trigger >> prompt_template_load_task >> history_prompt_build_task

    (
        trigger
        >> MapOperator(
            lambda req: ModelRequestContext(
                conv_uid=req.context.conv_uid,
                stream=req.stream,
                chat_mode=req.context.chat_mode,
            )
        )
        >> chat_history_load_task
        >> history_transform_task
        >> history_prompt_build_task
    )

    trigger >> MapOperator(parse_prompt_args) >> history_prompt_build_task

    history_prompt_build_task >> model_request_build_task
    trigger >> model_request_build_task

    model_request_build_task >> branch_task
    # The branch of no streaming response.
    (branch_task >> llm_task >> model_parse_task >> result_join_task)
    # The branch of streaming response.
    (branch_task >> streaming_llm_task >> openai_format_stream_task >> result_join_task)

if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag])
    else:
        pass
