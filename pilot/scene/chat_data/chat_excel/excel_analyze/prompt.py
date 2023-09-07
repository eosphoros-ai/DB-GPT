import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_data.chat_excel.excel_analyze.out_parser import (
    ChatExcelOutputParser,
)
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = "You are a data analysis expert. "

_DEFAULT_TEMPLATE_EN = """
Please use the data structure information of the above historical dialogue, make sure not to use column names that are not in the data structure.
According to the user goal: {user_input}，give the correct duckdb SQL for data analysis.
Use the table name: {table_name}

According to the analysis SQL obtained by the user's goal, select the best one from the following display forms, if it cannot be determined, use Text  as the display,Just need to return the type name into the result.
Display type: 
    {disply_type}
    
Respond in the following json format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads

"""

_DEFAULT_TEMPLATE_ZH = """
请使用上述历史对话中的数据结构和列信息，根据用户目标：{user_input}，给出正确的duckdb SQL进行数据分析和问题回答。
请确保不要使用不在数据结构中的列名。
SQL中需要使用的表名是: {table_name}

根据用户目标得到的分析SQL，请从以下显示类型中选择最合适的一种用来展示结果数据，如果无法确定，则使用'Text'作为显示, 只需要将类型名称返回到结果中。
显示类型如下: 
    {disply_type}

以以下 json 格式响应：:
    {response}
确保响应是正确的json,并且可以被Python的json.loads方法解析.
"""

RESPONSE_FORMAT_SIMPLE = {
    "sql": "analysis SQL",
    "thoughts": "Current thinking and value of data analysis",
    "display": "display type name",
}

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.8

prompt = PromptTemplate(
    template_scene=ChatScene.ChatExcel.value(),
    input_variables=["user_input", "table_name", "disply_type"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ChatExcelOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
    need_historical_messages=True,
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)
