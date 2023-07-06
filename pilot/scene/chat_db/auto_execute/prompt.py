import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.auto_execute.out_parser import DbChatOutputParser, SqlAction
from pilot.common.schema import SeparatorStyle
from pilot.scene.chat_db.auto_execute.example import sql_data_example

CFG = Config()

PROMPT_SCENE_DEFINE = None

_DEFAULT_TEMPLATE = """
You are a SQL expert. Given an input question, create a syntactically correct {dialect} sql.

Unless the user specifies in his question a specific number of examples he wishes to obtain, always limit your query to at most {top_k} results. 
Use as few tables as possible when querying.
Only use the following tables schema to generate sql:
{table_info}
Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.

Question: {input}

Rrespond in JSON format as following format:
{response}
Ensure the response is correct json and can be parsed by Python json.loads
"""

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "thoughts summary to say to user",
    "sql": "SQL Query to run",
}

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.5

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbExecute.value(),
    input_variables=["input", "table_info", "dialect", "top_k", "response"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
    example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_templates.update({prompt.template_scene: prompt})
