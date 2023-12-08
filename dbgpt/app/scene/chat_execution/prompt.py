import json
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene

from dbgpt.app.scene.chat_execution.out_parser import PluginChatOutputParser

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

### Whether the model service is streaming output
PROMPT_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ChatExecution.value(),
    input_variables=["input", "constraints", "commands_infos", "response"],
    response_format=json.dumps(RESPONSE_FORMAT, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=PluginChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    # example_selector=plugin_example,
)

CFG.prompt_template_registry.register(prompt, is_default=True)
