import json
import importlib
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.professional_qa.out_parser import NormalChatOutputParser
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = """A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. """

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
You are a database expert. you will be given metadata information about a database or table, and then provide a brief summary and answer to the question. For example, question: "How many tables are there in database 'db_gpt'?" , answer: "There are 5 tables in database 'db_gpt', which are 'book', 'book_category', 'borrower', 'borrowing', and 'category'.
Based on the database metadata information below, provide users with professional and concise answers to their questions. If the answer cannot be obtained from the provided content, please say: "The information provided in the knowledge base is not sufficient to answer this question." It is forbidden to make up information randomly.
database metadata information: 
{table_info}
question:
{input}
"""

_DEFAULT_TEMPLATE_ZH = """
你是一位数据库专家。你将获得有关数据库或表的元数据信息，然后提供简要的总结和回答。例如，问题：“数据库 'db_gpt' 中有多少个表？” 答案：“数据库 'db_gpt' 中有 5 个表，分别是 'book'、'book_category'、'borrower'、'borrowing' 和 'category'。”
根据以下数据库元数据信息，为用户提供专业简洁的答案。如果无法从提供的内容中获取答案，请说：“知识库中提供的信息不足以回答此问题。” 禁止随意捏造信息。
数据库元数据信息: 
{table_info}
问题:
{input}
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbQA.value,
    input_variables=["input", "table_info"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_templates.update({prompt.template_scene: prompt})
