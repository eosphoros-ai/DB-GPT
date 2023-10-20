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
Given an input question, create a syntactically correct {dialect} sql.
Table structure information:
             {table_info}
Constraint:
1. You can only use the table provided in the table structure information to generate sql. If you cannot generate sql based on the provided table structure, please say: "The table structure information provided is not enough to generate sql query." It is prohibited to fabricate information at will.
2. Do not query columns that do not exist. Pay attention to which column is in which table.
3. Replace the corresponding sql into the sql field in the returned result
4. Unless the user specifies in the question a specific number of examples he wishes to obtain, always limit the query to a maximum of {top_k} results.
5. Please output the Sql content in the following format to execute the corresponding SQL to display the data:<api-call><name>response_table</name><args><sql>SQL Query to run</sql></args></api-call>
Please make sure to respond as following format:
    thoughts summary to say to user.<api-call><name>response_table</name><args><sql>SQL Query to run</sql></args></api-call>
    
Question: {input}
"""

_DEFAULT_TEMPLATE_ZH = """
给定一个输入问题，创建一个语法正确的 {dialect} sql。
已知表结构信息:
    {table_info}

约束:
1. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：“提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
2. 不要查询不存在的列，注意哪一列位于哪张表中。
3.将对应的sql替换到返回结果中的sql字段中
4.除非用户在问题中指定了他希望获得的具体示例数量，否则始终将查询限制为最多 {top_k} 个结果。

请务必按照以下格式回复：
   对用户说的想法摘要。<api-call><name>response_table</name><args><sql>要运行的 SQL</sql></args></api-call>
   
问题:{input}
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

PROMPT_NEED_NEED_STREAM_OUT = True

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.5

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbExecute.value(),
    input_variables=["input", "table_info", "dialect", "top_k", "response"],
    # response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)
from . import prompt_baichuan
