import builtins
import importlib
import json

from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_knowledge.inner_db_summary.out_parser import (
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


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.InnerChatDBSummary.value(),
    input_variables=["db_profile_summary", "db_input", "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)


CFG.prompt_templates.update({prompt.template_scene: prompt})
