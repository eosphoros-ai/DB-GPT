from dbgpt._private.config import Config
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)
from dbgpt_app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt_app.scene.chat_db.professional_qa.out_parser import NormalChatOutputParser

CFG = Config()


_DEFAULT_TEMPLATE_EN = """
Provide professional answers to requests and questions. If you can't get an answer \
from what you've provided, say: "Insufficient information in the knowledge base is \
available to answer this question." Feel free to fudge information.
Use the following tables generate sql if have any table info:
{table_info}

NOTE: this is a QA-only scene; you cannot execute SQL here. The table list \
above contains only the TOP-K most relevant tables retrieved from a vector \
store; it is NOT the complete list of tables in the database. If the user \
asks for a total count of tables, a list of all tables, a schema overview, \
or any other metadata that requires knowing the whole database, do NOT \
answer with a count or list derived from the partial table list above. \
Instead, acknowledge the limitation and show the SQL query against \
INFORMATION_SCHEMA (or the dialect-specific system catalog) that the user \
can run in a SQL-executing scene to obtain the answer.

user question:
{input}
think step by step.
"""

_DEFAULT_TEMPLATE_ZH = """
根据要求和问题，提供专业的答案。如果无法从提供的内容中获取答案，请说：\
“知识库中提供的信息不足以回答此问题。” 禁止随意捏造信息。

使用以下表结构信息:
{table_info}

注意：这是只问答（QA）场景，无法在此处执行 SQL。以上表清单只是从向量库\
检索到的 TOP-K 最相关表，并非数据库中所有表的完整清单。当用户询问表的\
总数、所有表的列表、schema 结构总览，或其他需要了解整个数据库元信息的\
问题时，请勿根据以上部分表清单直接给出数量或列表。请说明此限制，并展示\
可在「可执行 SQL」场景中运行、针对 INFORMATION_SCHEMA（或方言对应的系统\
目录）的 SQL 查询，以便用户取得正确答案。

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
    output_parser=NormalChatOutputParser(),
)


CFG.prompt_template_registry.register(
    prompt_adapter, language=CFG.LANGUAGE, is_default=True
)
