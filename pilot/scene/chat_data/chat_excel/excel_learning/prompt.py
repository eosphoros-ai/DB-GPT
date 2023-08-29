import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_data.chat_excel.excel_learning.out_parser import (
    LearningExcelOutputParser,
)
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = "You are a data analysis expert. "

_DEFAULT_TEMPLATE_EN = """
This is an example data，please learn to understand the structure and content of this data:
    {data_example}
Explain the meaning and function of each column, and give a simple and clear explanation of the technical terms.  
Provide some analysis options,please think step by step.

Please return your answer in JSON format, the return format is as follows:
    {response}
"""

_DEFAULT_TEMPLATE_ZH = """
下面是一份示例数据，请学习理解该数据的结构和内容:
    {data_example}
分析各列数据的含义和作用，并对专业术语进行简单明了的解释。
提供一些分析方案思路，请一步一步思考。

请以JSON格式返回您的答案，返回格式如下：
    {response}
"""

RESPONSE_FORMAT_SIMPLE = {
    "DataAnalysis": "数据内容分析总结",
    "ColumnAnalysis": [{"column name1": "字段1介绍，专业术语解释(请尽量简单明了)"}],
    "AnalysisProgram": ["1.分析方案1，图表展示方式1", "2.分析方案2，图表展示方式2"],
}

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.5

prompt = PromptTemplate(
    template_scene=ChatScene.ExcelLearning.value(),
    input_variables=["data_example"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=LearningExcelOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)
