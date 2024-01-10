from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_db.professional_qa.out_parser import NormalChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

CFG = Config()


_DEFAULT_TEMPLATE_EN = """
Provide professional answers to requests and questions. If you can't get an answer from what you've provided, say: "Insufficient information in the knowledge base is available to answer this question." Feel free to fudge information.
Use the following tables generate sql if have any table info:
{table_info}

user question:
{input}
think step by step.
"""

_DEFAULT_TEMPLATE_ZH = """
根据要求和问题，提供专业的答案。如果无法从提供的内容中获取答案，请说：“知识库中提供的信息不足以回答此问题。” 禁止随意捏造信息。

使用以下表结构信息: 
{table_info}

问题:
{input}
一步步思考。
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


PROMPT_NEED_STREAM_OUT = True


prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(_DEFAULT_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatWithDbQA.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=True,
)


CFG.prompt_template_registry.register(
    prompt_adapter, language=CFG.LANGUAGE, is_default=True
)
