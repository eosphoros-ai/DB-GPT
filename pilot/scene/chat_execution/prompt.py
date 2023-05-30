import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_execution.out_parser import PluginChatOutputParser


CFG = Config()

PROMPT_SCENE_DEFINE = """You are an AI designed to solve the user's goals with given commands, please follow the prompts and constraints of the system's input for your answers.Play to your strengths as an LLM and pursue simple strategies with no legal complications."""

PROMPT_SUFFIX = """
Goals: 
    {input}
    
"""

_DEFAULT_TEMPLATE = """
Constraints:
    Exclusively use the commands listed in double quotes e.g. "command name"
    Reflect on past decisions and strategies to refine your approach.
    Constructively self-criticize your big-picture behavior constantly.
    {constraints}
    
Commands:
    {commands_infos}
"""


PROMPT_RESPONSE = """You must respond in JSON format as following format:
{response}

Ensure the response is correct json and can be parsed by Python json.loads
"""

RESPONSE_FORMAT = {
    "thoughts": {
        "text": "thought",
        "reasoning": "reasoning",
        "plan": "- short bulleted\n- list that conveys\n- long-term plan",
        "criticism": "constructive self-criticism",
        "speak": "thoughts summary to say to user",
    },
    "command": {"name": "command name", "args": {"arg name": "value"}},
}

PROMPT_SEP = SeparatorStyle.SINGLE.value
### Whether the model service is streaming output
PROMPT_NEED_NEED_STREAM_OUT = False

chat_plugin_prompt = PromptTemplate(
    template_scene=ChatScene.ChatExecution.value,
    input_variables=["input", "constraints", "commands_infos",  "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=PROMPT_SUFFIX + _DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=PluginChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_templates.update({chat_plugin_prompt.template_scene: chat_plugin_prompt})
