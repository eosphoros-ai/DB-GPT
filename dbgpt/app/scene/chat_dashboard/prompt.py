import json
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.app.scene.chat_dashboard.out_parser import ChatDashboardOutputParser

CFG = Config()

PROMPT_SCENE_DEFINE = "You are a data analysis expert, please provide a professional data analysis solution"

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


PROMPT_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ChatDashboard.value(),
    input_variables=["input", "table_info", "dialect", "supported_chat_type"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=ChatDashboardOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
)
CFG.prompt_template_registry.register(prompt, is_default=True)
