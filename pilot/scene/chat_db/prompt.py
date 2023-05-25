import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.out_parser import DbChatOutputParser, SqlAction
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = """You are an AI designed to answer human questions, please follow the prompts and conventions of the system's input for your answers"""

PROMPT_SUFFIX = """Only use the following tables:
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

_mysql_prompt = """You are a MySQL expert. Given an input question, first create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer to the input question.
Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per MySQL. You can order the results to return the most informative data in the database.
Never query for all columns from a table. You must query only the columns that are needed to answer the question. Wrap each column name in backticks (`) to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
Pay attention to use CURDATE() function to get the current date, if the question involves "today".


"""

PROMPT_RESPONSE = """You must respond in JSON format as following format:
{response}

Ensure the response is correct json and can be parsed by Python json.loads
"""

RESPONSE_FORMAT = {
    "thoughts": {
        "reasoning": "reasoning",
        "speak": "thoughts summary to say to user",
    },
    "sql": "SQL Query to run",
}

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

chat_db_prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDb.value,
    input_variables=["input", "table_info", "dialect", "top_k", "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_SUFFIX + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_templates.update({chat_db_prompt.template_scene: chat_db_prompt})
