import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle, ExampleType

from pilot.scene.chat_execution.out_parser import PluginChatOutputParser
from pilot.scene.chat_execution.example import plugin_example

CFG = Config()

PROMPT_SCENE_DEFINE = "You are an AI designed to solve the user's goals with given commands, please follow the  constraints of the system's input for your answers."

_DEFAULT_TEMPLATE = """
Goals: 
    {input}
    
Constraints:
0.Exclusively use the commands listed in double quotes e.g. "command name"
{constraints}
    
Commands:
{commands_infos}

Please response strictly according to the following json format:
{response}
Ensure the response is correct json and can be parsed by Python json.loads
"""

RESPONSE_FORMAT = {
    "thoughts": "thought text",
    "speak": "thoughts summary to say to user",
    "command": {"name": "command name", "args": {"arg name": "value"}},
}


EXAMPLE_TYPE = ExampleType.ONE_SHOT
PROMPT_SEP = SeparatorStyle.SINGLE.value
### Whether the model service is streaming output
PROMPT_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ChatExecution.value(),
    input_variables=["input", "constraints", "commands_infos", "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=PluginChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_STREAM_OUT
    ),
    example_selector=plugin_example,
)

CFG.prompt_templates.update({prompt.template_scene: prompt})
