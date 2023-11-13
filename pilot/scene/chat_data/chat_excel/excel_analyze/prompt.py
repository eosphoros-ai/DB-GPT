import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_data.chat_excel.excel_analyze.out_parser import (
    ChatExcelOutputParser,
)
from pilot.common.schema import SeparatorStyle

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a data analysis expert. "

_DEFAULT_TEMPLATE_EN = """
Please use the data structure and column information in the above historical dialogue and combine it with data analysis to answer the user's questions while satisfying the constraints.

Constraint:
    1.Please output your thinking process and analysis ideas first, and then output the specific data analysis results. The data analysis results are output in the following format:<api-call><name>display type</name><args><sql>Correct duckdb data analysis sql</sql></args></api-call> 
    2.For the available display methods of data analysis results, please choose the most appropriate one from the following display methods. If you are not sure, use 'response_data_text' as the display. The available display types are as follows:{disply_type}
    3.The table name that needs to be used in SQL is: {table_name}, please make sure not to use column names that are not in the data structure.
    4.Give priority to answering using data analysis. If the user's question does not involve data analysis, you can answer according to your understanding.

User Questions:
    {user_input}
"""

_PROMPT_SCENE_DEFINE_ZH = """你是一个数据分析专家！"""
_DEFAULT_TEMPLATE_ZH = """
请使用上述历史对话中的数据结构信息，在满足下面约束条件下结合数据分析回答用户的问题。
约束条件:
	1.请先输出你的分析思路内容，再输出具体的数据分析结果。如果有数据数据分析时，请确保在输出的结果中包含如下格式内容:<api-call><name>[数据展示方式]</name><args><sql>[正确的duckdb数据分析sql]</sql></args></api-call> 
	2.请确保数据分析结果格式的内容在整个回答中只出现一次,确保上述结构稳定，把[]部分内容替换为对应的值
	3.数据分析结果可用的展示方式请在下面的展示方式中选择最合适的一种,放入数据分析结果的name字段内如果无法确定，则使用'Text'作为显示，可用数据展示方式如下: {disply_type}
	4.SQL中需要使用的表名是: {table_name},请不要使用没在数据结构中的列名。
	5.优先使用数据分析的方式回答，如果用户问题不涉及数据分析内容，你可以按你的理解进行回答
	6.请确保你的输出内容有良好排版，输出内容均为普通markdown文本,不要用```或者```python这种标签来包围<api-call>的输出内容
请确保你的输出格式如下:
    分析思路简介.<api-call><name>[数据展示方式]</name><args><sql>[正确的duckdb数据分析sql]</sql></args></api-call>

用户问题：{user_input}
"""


_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

_PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_STREAM_OUT = True

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.8

prompt = PromptTemplate(
    template_scene=ChatScene.ChatExcel.value(),
    input_variables=["user_input", "table_name", "disply_type"],
    template_define=_PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=ChatExcelOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_STREAM_OUT
    ),
    need_historical_messages=True,
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)
