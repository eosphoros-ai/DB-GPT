import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.auto_execute.out_parser import DbChatOutputParser
from pilot.common.schema import SeparatorStyle
from pilot.scene.chat_db.auto_execute.example import sql_data_example

CFG = Config()


_PROMPT_SCENE_DEFINE_EN = "You are a database expert. "
_PROMPT_SCENE_DEFINE_ZH = "你是一个数据库专家. "

_DEFAULT_TEMPLATE_EN = """
Please create a syntactically correct {dialect} sql based on the user question, use the following tables schema to generate sql:
    {table_info}

Constraint:
    1.Unless the user specifies in his question a specific number of examples he wishes to obtain, always limit your query to at most {top_k} results. 
    2.Please do not use columns that do not appear in the tables schema. Also be careful not to misunderstand the relationship between fields and tables in SQL.
    3.Use as few tables as possible when querying.
    4.Please check the correctness of the SQL and ensure that the query performance is optimized under correct conditions.
    
Please think step by step and respond according to the following JSON format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads.

"""

_DEFAULT_TEMPLATE_ZH = """
请根据用户输入问题，使用如下的表结构定义创建一个语法正确的 {dialect} sql:
    {table_info}

约束:
    1. 除非用户在问题中指定了他希望获得的具体数据行数，否则始终将查询限制为最多 {top_k} 个结果。
    2. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：“提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
    3. 请注意生成SQL时不要弄错表和列的关系
    4. 请检查SQL的正确性，并保证正确的情况下优化查询性能

请一步步思考并按照以下JSON格式回复：
      {response}
确保返回正确的json并且可以被Python json.loads方法解析.

"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "thoughts summary to say to user",
    "sql": "SQL Query to run",
}

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.5

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbExecute.value(),
    input_variables=["table_info", "dialect", "top_k", "response"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_STREAM_OUT
    ),
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
    need_historical_messages=True
)
CFG.prompt_template_registry.register(prompt, is_default=True)
from . import prompt_baichuan
