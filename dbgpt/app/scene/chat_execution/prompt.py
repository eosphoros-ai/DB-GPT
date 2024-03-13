import json

from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_execution.out_parser import PluginChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

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

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            PROMPT_SCENE_DEFINE + _DEFAULT_TEMPLATE,
            response_format=json.dumps(RESPONSE_FORMAT, indent=4),
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatExecution.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=PluginChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=False,
)

CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
