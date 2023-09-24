import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_dashboard.out_parser import ChatDashboardOutputParser, ChartItem
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = "你是一个数据分析专家，请提供专业的数据分析解决方案"

_DEFAULT_TEMPLATE = """
根据以下表结构定义：
{table_info}
提供专业的数据分析以支持用户的目标：
{input}

根据用户目标，提供至少4个，最多8个维度的分析。
分析的输出数据不能超过4列，不要在SQL where条件中使用如pay_status之类的列进行数据筛选。
根据分析数据的特性，从下面提供的图表中选择最合适的一种进行数据展示，图表类型：
{supported_chat_type}

注意分析结果的输出内容长度，不要超过4000个令牌

给出正确的{dialect}分析SQL
1.不要使用未提供的值，如'paid'
2.所有查询的值必须是有别名的，如select count(*) as count from table
3.如果表结构定义使用了{dialect}的关键字作为字段名，需要使用转义符，如select `count` from table
4.仔细检查SQL的正确性，SQL必须是正确的，显示方法和简要分析思路的总结，并以以下json格式回应：
{response}
做重要的额是:请确保只返回json字符串，不要添加任何其他内容(用于程序直接处理),并且json并能被Python json.loads解析
"""

RESPONSE_FORMAT = [
    {
        "sql": "data analysis SQL",
        "title": "Data Analysis Title",
        "showcase": "What type of charts to show",
        "thoughts": "Current thinking and value of data analysis",
    }
]

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ChatDashboard.value(),
    input_variables=["input", "table_info", "dialect", "supported_chat_type"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ChatDashboardOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)
CFG.prompt_template_registry.register(prompt, is_default=True)
