from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.app.scene.chat_db.professional_qa.out_parser import NormalChatOutputParser

CFG = Config()

PROMPT_SCENE_DEFINE = (
    """You are an assistant that answers user specialized database questions. """
)

# PROMPT_SUFFIX = """Only use the following tables generate sql if have any table info:
# {table_info}
#
# Question: {input}
#
# """

# _DEFAULT_TEMPLATE = """
# You are a SQL expert. Given an input question, first create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
# Unless the user specifies in his question a specific number of examples he wishes to obtain, always limit your query to at most {top_k} results.
# You can order the results by a relevant column to return the most interesting examples in the database.
# Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.
# Pay attention to use only the column names that you can see in the schema description. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
#
# """

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
一步步思考
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


PROMPT_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbQA.value(),
    input_variables=["input", "table_info"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, language=CFG.LANGUAGE, is_default=True)
