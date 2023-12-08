from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.app.scene.chat_data.chat_excel.excel_analyze.out_parser import (
    ChatExcelOutputParser,
)

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a data analysis expert. "

_DEFAULT_TEMPLATE_EN = """
Please use the data structure column analysis information generated in the above historical dialogue to answer the user's questions through duckdb sql data analysis under the following constraints..

Constraint:
    1.Please fully understand the user's problem and use duckdb sql for analysis. The analysis content is returned in the output format required below. Please output the sql in the corresponding sql parameter.
    2.Please choose the best one from the display methods given below for data rendering, and put the type name into the name parameter value that returns the required format. If you cannot find the most suitable one, use 'Table' as the display method. , the available data display methods are as follows: {disply_type}
    3.The table name that needs to be used in SQL is: {table_name}. Please check the sql you generated and do not use column names that are not in the data structure.
    4.Give priority to answering using data analysis. If the user's question does not involve data analysis, you can answer according to your understanding.
    5.The sql part of the output content is converted to: <api-call><name>[data display mode]</name><args><sql>[correct duckdb data analysis sql]</sql></args></api - call> For this format, please refer to the return format requirements.
    
Please think step by step and give your answer, and make sure your answer is formatted as follows:
    thoughts summary to say to user.<api-call><name>[Data display method]</name><args><sql>[Correct duckdb data analysis sql]</sql></args></api-call>
    
User Questions:
    {user_input}
"""

_PROMPT_SCENE_DEFINE_ZH = """你是一个数据分析专家！"""
_DEFAULT_TEMPLATE_ZH = """
请使用历史对话中的数据结构信息，在满足下面约束条件下通过duckdb sql数据分析回答用户的问题。
约束条件:
	1.请充分理解用户的问题，使用duckdb sql的方式进行分析， 分析内容按下面要求的输出格式返回，sql请输出在对应的sql参数中
	2.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值种，如果找不到最合适的则使用'Table'作为展示方式，可用数据展示方式如下: {disply_type}
	3.SQL中需要使用的表名是: {table_name},请检查你生成的sql，不要使用没在数据结构中的列名
	4.优先使用数据分析的方式回答，如果用户问题不涉及数据分析内容，你可以按你的理解进行回答
	5.输出内容中sql部分转换为：<api-call><name>[数据显示方式]</name><args><sql>[正确的duckdb数据分析sql]</sql></args></api- call> 这样的格式，参考返回格式要求
	
请一步一步思考，给出回答，并确保你的回答内容格式如下:
    对用户说的想法摘要.<api-call><name>[数据展示方式]</name><args><sql>[正确的duckdb数据分析sql]</sql></args></api-call>

用户问题：{user_input}
"""


_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

_PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)


PROMPT_NEED_STREAM_OUT = True

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.3

prompt = PromptTemplate(
    template_scene=ChatScene.ChatExcel.value(),
    input_variables=["user_input", "table_name", "disply_type"],
    template_define=_PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=ChatExcelOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=True,
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)
