import json

from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene

from dbgpt.app.scene.chat_knowledge.inner_db_summary.out_parser import (
    NormalChatOutputParser,
)


CFG = Config()

PROMPT_SCENE_DEFINE = """"""

_DEFAULT_TEMPLATE = """
Based on the following known database information?, answer which tables are involved in the user input.
Known database information:{db_profile_summary}
Input:{db_input}
You should only respond in JSON format as described below and ensure the response can be parsed by Python json.loads


"""
PROMPT_RESPONSE = """You must respond in JSON format as following format:
{response}
The response format must be JSON, and the key of JSON must be "table".
"""


RESPONSE_FORMAT = {"table": ["orders", "products"]}


PROMPT_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.InnerChatDBSummary.value(),
    input_variables=["db_profile_summary", "db_input", "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
