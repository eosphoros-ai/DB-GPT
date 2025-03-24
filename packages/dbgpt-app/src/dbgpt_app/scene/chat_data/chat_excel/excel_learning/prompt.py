import json

from dbgpt._private.config import Config
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    SystemPromptTemplate,
)
from dbgpt_app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt_app.scene.chat_data.chat_excel.excel_learning.out_parser import (
    LearningExcelOutputParser,
)

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a data analysis expert. "
_DEFAULT_TEMPLATE_EN = """
You are provided with user data and asked to understand and respond according to the \
requirements below.
The data is currently in a DuckDB table, \
a sample of which is as follows:
``````json
{data_example}
``````
The table summary information is as follows:
``````json
{table_summary}
``````
The DuckDB table structure information is as follows:
{table_schema}
Analyze the meaning and function of each column of data, and provide simple and clear \
explanations of technical terms, \
with the following specific requirements:
1. Carefully read the table structure, data samples, and table summary information \
provided to you
2. Extract information such as column names, data types, data meanings, data formats, \
etc. 3. To standardize the data structure, I need to transform the original column \
names, such as converting "年龄" to "age", "Completion progress" to \
"completion_progress", etc.
4. You need to provide the original column names, transformed column names, \
data types, data meanings, data formats, etc.
5. If it's a time type, please provide the time format, such as: yyyy-MM-dd HH:MM:ss.
6. Please provide some useful analysis ideas from different dimensions for the user \
(arranged in order from simple to complex analysis complexity)
7. You need to output the extracted information according to the format below, \
ensuring that the output format is correct Column name conversion rules:
1. If it's in English letters, convert them all to lowercase, and replace spaces with \
underscores
2. If it's numbers, keep them as is
3. If it's Chinese, translate the Chinese field names to English, and replace spaces \
with underscores
4. If it's in other languages, translate them to English, and replace spaces with \
underscores
5. If it's special characters, delete them directly
6. DuckDB adheres to the SQL standard, which requires that identifiers \
(column names, table names) cannot start with a number.
7. All column fields must be analyzed and converted, remember to output in JSON
Avoid phrases like ' // ... (similar analysis for other columns) ...'
8. You need to provide the original column names and the transformed new column names \
in the JSON, as well as your analysis of the meaning and function of that column. If \
it's a time type, please provide the time format, such as: \
yyyy-MM-dd HH:MM:ss
You must output JSON data, where:
The `data_analysis` property is a summary of the data content analysis, \
The `column_analysis` is a JSON array type containing the conversion and analysis \
results for each column, \
The `analysis_program` property is the analysis approach.
Please think step by step, ensure that you answer only in JSON format, and ensure it \
can be parsed by Python's json.loads() function.
Response format is as follows:
```json
    {response}
```
"""

_PROMPT_SCENE_DEFINE_ZH = "你是一个数据分析专家. "

_DEFAULT_TEMPLATE_ZH = """
给你一份用户的数据, 请你对数据理解并根据下面的要求响应用户，
目前数据在 DuckDB 表中，\

一部分采样数据如下:
``````json
{data_example}
``````

表的摘要信息如下:
``````json
{table_summary}
``````

DuckDB 表结构信息如下：
{table_schema}


分析各列数据的含义和作用，并对专业术语进行简单明了的解释, \
具体要求：
1. 仔细阅读给你的表结构、数据样例和表摘要信息
2. 提取出字段的列名、数据类型、数据含义、数据格式等信息
3. 为了标准化数据结构数据，我需要对于原来的列名进行转化，\
如将“年龄”转换为“age”, "Completion progress"转化为\
"completion_progress"等
4. 你需要提供原始的列名、转化后的列名、数据类型、数据含义、数据格式等信息
5. 如果是时间类型请给出时间格式类似:yyyy-MM-dd HH:MM:ss.
6. 请你针对数据从不同维度提供一些有用的分析思路给用户\
(可以按照分析复杂度从简单到复杂依次提供）
7. 你需要将提取的信息按照下面的格式输出，确保输出的格式正确


列名的转换规则:
1. 如果是英文字母，全部转换为小写，并且将空格替换为下划线
2. 如果是数字，直接保留
3. 如果是中文，将中文字段名翻译为英文，并且将空格替换为下划线
4. 如果是其它语言，将其翻译为英文，并且将空格替换为下划线
5. 如果是特殊字符，直接删除
6. DuckDB遵循SQL标准，要求标识符(列名、表名)不能以数字开头
7. 所以列的字段都必须分析和转换，切记在 JSON 中输出
' // ... (其他列的类似分析) ...)' 之类的话术
8. 你需要在json中提供原始列名和转化后的新的列名，以及你分析\
的该列的含义和作用，如果是时间类型请给出时间格式类似:\
yyyy-MM-dd HH:MM:ss

你必须输出 JSON 数据，其中:
`data_analysis` 属性是数据内容分析总结，\
`column_analysis` 是一个json数组类型，里面包含了每一列的转换、分析结果，\
`analysis_program` 属性是分析思路。

请一步一步思考,确保只以JSON格式回答，并且需要能被 Python 的 json.loads() 函数解析。
响应格式如下:
```json
    {response}
```
"""

_RESPONSE_FORMAT_SIMPLE_ZH = {
    "data_analysis": "数据内容分析总结",
    "column_analysis": [
        {
            "old_column_name": "原始列名",
            "new_column_name": "转换后的新的列名",
            "column_description": "字段1介绍，专业术语解释(请尽量简单明了)",
        }
    ],
    "analysis_program": ["1.分析方案1", "2.分析方案2"],
}
_RESPONSE_FORMAT_SIMPLE_EN = {
    "data_analysis": "Data content analysis summary",
    "column_analysis": [
        {
            "old_column_name": "Original column name",
            "new_column_name": "Converted new column name",
            "column_description": "Description of field 1, explanation of professional "
            "terms (as simple and clear as possible)",
        }
    ],
    "analysis_program": ["1. Analysis plan ", "2. Analysis plan "],
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

_USER_INPUT = "Please analyze the data for you"
_USER_INPUT_ZH = "请分析给你的数据"

USER_INPUT = _USER_INPUT if CFG.LANGUAGE == "en" else _USER_INPUT_ZH


PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of
# language model output.
# A high temperature produces more unpredictable and creative results, while a low
# temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate
# text that is more predictable and less creative than if you set the temperature to
# 1.0.
PROMPT_TEMPERATURE = 0.8

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            PROMPT_SCENE_DEFINE + _DEFAULT_TEMPLATE,
            response_format=json.dumps(
                RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4
            ),
        ),
        HumanPromptTemplate.from_template("{user_input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ExcelLearning.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=LearningExcelOutputParser(),
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
