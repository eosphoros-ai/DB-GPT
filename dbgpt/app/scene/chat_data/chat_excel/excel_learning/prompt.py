import json
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.app.scene.chat_data.chat_excel.excel_learning.out_parser import (
    LearningExcelOutputParser,
)

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a data analysis expert. "

_DEFAULT_TEMPLATE_EN = """
The following is part of the data of the user file {file_name}. Please learn to understand the structure and content of the data and output the parsing results as required:
    {data_example}
Explain the meaning and function of each column, and give a simple and clear explanation of the technical terms， If it is a Date column, please summarize the Date format like: yyyy-MM-dd HH:MM:ss.
Use the column name as the attribute name and the analysis explanation as the attribute value to form a json array and output it in the ColumnAnalysis attribute that returns the json content.
Please do not modify or translate the column names, make sure they are consistent with the given data column names.
Provide some useful analysis ideas to users from different dimensions for data.

Please think step by step and give your answer. Make sure to answer only in JSON format，the format is as follows:
    {response}
"""

_PROMPT_SCENE_DEFINE_ZH = "你是一个数据分析专家. "

_DEFAULT_TEMPLATE_ZH = """
下面是用户文件{file_name}的一部分数据，请学习理解该数据的结构和内容，按要求输出解析结果:
    {data_example}
分析各列数据的含义和作用，并对专业术语进行简单明了的解释, 如果是时间类型请给出时间格式类似:yyyy-MM-dd HH:MM:ss.
将列名作为属性名，分析解释作为属性值,组成json数组，并输出在返回json内容的ColumnAnalysis属性中.
请不要修改或者翻译列名，确保和给出数据列名一致.
针对数据从不同维度提供一些有用的分析思路给用户。

请一步一步思考,确保只以JSON格式回答，具体格式如下：
    {response}
"""

_RESPONSE_FORMAT_SIMPLE_ZH = {
    "DataAnalysis": "数据内容分析总结",
    "ColumnAnalysis": [{"column name": "字段1介绍，专业术语解释(请尽量简单明了)"}],
    "AnalysisProgram": ["1.分析方案1", "2.分析方案2"],
}
_RESPONSE_FORMAT_SIMPLE_EN = {
    "DataAnalysis": "Data content analysis summary",
    "ColumnAnalysis": [
        {
            "column name": "Introduction to Column 1 and explanation of professional terms (please try to be as simple and clear as possible)"
        }
    ],
    "AnalysisProgram": ["1. Analysis plan ", "2. Analysis plan "],
}

RESPONSE_FORMAT_SIMPLE = (
    _RESPONSE_FORMAT_SIMPLE_EN if CFG.LANGUAGE == "en" else _RESPONSE_FORMAT_SIMPLE_ZH
)


_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)


PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.8

prompt = PromptTemplate(
    template_scene=ChatScene.ExcelLearning.value(),
    input_variables=["data_example"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=LearningExcelOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)
