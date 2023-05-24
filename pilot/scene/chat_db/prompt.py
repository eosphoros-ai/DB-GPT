import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.out_parser import DbChatOutputParser

CFG = Config()

PROMPT_SCENE_DEFINE = """"""

PROMPT_SUFFIX = """Only use the following tables:
{table_info}

Question: {input}

"""

_DEFAULT_TEMPLATE = """Given an input question, first create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
Unless the user specifies in his question a specific number of examples he wishes to obtain, always limit your query to at most {top_k} results. 
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for a the few relevant columns given the question.
Pay attention to use only the column names that you can see in the schema description. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.

"""

PROMPT_RESPONSE = """You should only respond in JSON format as  following format:
{response}

Ensure the response can be parsed by Python json.loads
"""

RESPONSE_FORMAT = {
    "thoughts": {
        "reasoning": "reasoning",
        "speak": "thoughts summary to say to user",
    },
    "SQL": "SQL Query to run"
}

chat_db_prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDb.value,
    input_variables=["input", "table_info", "dialect", "top_k", "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template=_DEFAULT_TEMPLATE + PROMPT_SUFFIX + PROMPT_RESPONSE,
    output_parser=DbChatOutputParser()
)

CFG.prompt_templates.update({chat_db_prompt.template_scene: chat_db_prompt})


if __name__ == "__main__":
    resp = chat_db_prompt.format(input="查询用户信息", table_info="user(a,b,c,d)", dialect="mysql", top_k=10)
    print(resp)
