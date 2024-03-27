import json

from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_dashboard.out_parser import ChatDashboardOutputParser
from dbgpt.core import ChatPromptTemplate, HumanPromptTemplate, SystemPromptTemplate

CFG = Config()

PROMPT_SCENE_DEFINE = f"You are a data analysis expert, please provide a professional data analysis solution. please use {'中文' if CFG.LANGUAGE=='zh' else 'English' } to answer"
PROMPT_SCENE_DEFINE_zh = f"您是数据分析专家，请提供专业的数据分析解决方案. 请用{'中文' if CFG.LANGUAGE=='zh' else 'English' }进行回答。"



_DEFAULT_TEMPLATE_zh = """
根据下表结构定义：
{table_info}
提供专业的数据分析，支持用户实现目标：
{input}

根据用户目标提供至少 4 个、最多 8 个维度的分析.
分析的输出数据不能超过4列，并且不要使用SQL中pay_status等列进行数据过滤。
根据分析数据的特征，从下面提供的图表中选择最合适的一个进行数据显示，图表类型：
{supported_chat_type}

注意分析结果输出内容的长度，不要超过4000个令牌

给出正确的 {dialect} 分析 SQL
1.不使用未提供的值，例如“已支付”
2.所有查询的值都必须具有别名，例如select count（） as count from table
3.如果表结构定义使用 {dialect} 的关键字作为字段名称，则需要使用转义字符，例如从表中选择“count”
4.请一步一步的仔细检查SQL的正确性，SQL必须正确，展示方法和总结的简要分析思路，并按以下json格式回复：
{response}
重要的是：请确保只返回 json 字符串，不要添加任何其他内容（供程序直接处理），并且 json 可以被 Python 解析 json.loads
"""

_DEFAULT_TEMPLATE = """
According to the following table structure definition:
{table_info}
Provide professional data analysis to support users' goals:
{input}

Provide at least 4 and at most 8 dimensions of analysis according to user goals.
The output data of the analysis cannot exceed 4 columns, and do not use columns such as pay_status in the SQL where condition for data filtering.
According to the characteristics of the analyzed data, choose the most suitable one from the charts provided below for data display, chart type:
{supported_chat_type}

Pay attention to the length of the output content of the analysis result, do not exceed 4000 tokens

Give the correct {dialect} analysis SQL
1.Do not use unprovided values such as 'paid'
2.All queried values must have aliases, such as select count(*) as count from table
3.If the table structure definition uses the keywords of {dialect} as field names, you need to use escape characters, such as select `count` from table
4.Carefully check the correctness of the SQL, the SQL must be correct, display method and summary of brief analysis thinking, and respond in the following json format:
{response}
The important thing is: Please make sure to only return the json string, do not add any other content (for direct processing by the program), and the json can be parsed by Python json.loads
"""

RESPONSE_FORMAT = [
    {
        "sql": "data analysis SQL",
        "title": "Data Analysis Title",
        "showcase": "What type of charts to show",
        "thoughts": "Current thinking and value of data analysis",
    }
]
RESPONSE_FORMAT_zh = [
    {
        "sql": "数据分析 SQL",
        "title": "数据分析的标题",
        "showcase": "要显示的图表类型",
        "thoughts": "数据分析的当前想法和价值",
    }
]

PROMPT_NEED_STREAM_OUT = False

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            PROMPT_SCENE_DEFINE + _DEFAULT_TEMPLATE if CFG.LANGUAGE == "en" else PROMPT_SCENE_DEFINE_zh + _DEFAULT_TEMPLATE_zh,
            response_format=json.dumps(RESPONSE_FORMAT, indent=4),
        ),
        HumanPromptTemplate.from_template("{input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatDashboard.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=ChatDashboardOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=False,
)
CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
