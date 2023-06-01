import json
import importlib
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.professional_qa.out_parser import NormalChatOutputParser
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = """A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. """

PROMPT_SUFFIX = """Only use the following tables generate sql if have any table info:
{table_info}

Question: {input}

"""

_DEFAULT_TEMPLATE = """
You are a SQL expert. Given an input question, first create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
Unless the user specifies in his question a specific number of examples he wishes to obtain, always limit your query to at most {top_k} results. 
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.
Pay attention to use only the column names that you can see in the schema description. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.

"""



PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbQA.value,
    input_variables=["input", "table_info", "dialect", "top_k"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_SUFFIX ,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_templates.update({prompt.template_scene: prompt})

