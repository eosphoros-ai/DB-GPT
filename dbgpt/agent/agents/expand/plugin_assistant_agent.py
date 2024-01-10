import logging
from pathlib import Path
from typing import Callable, Dict, Literal, Optional, Union

from dbgpt.util.json_utils import find_json_objects
from dbgpt.vis import VisPlugin, vis_client

from ...common.schema import Status
from ...memory.gpts_memory import GptsMemory
from ...plugin.commands.command_mange import execute_command
from ...plugin.loader import PluginLoader
from ..agent import Agent, AgentContext
from ..base_agent import ConversableAgent

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x


# TODO
from dbgpt.configs.model_config import PLUGINS_DIR

logger = logging.getLogger(__name__)


class PluginAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """
    You are a useful artificial intelligence tool agent assistant.
    You have been assigned the following list of tools, please select the most appropriate tool to complete the task based on the current user's goals:
        {tool_list}
        
    *** IMPORTANT REMINDER ***
    Please read the parameter definition of the tool carefully and extract the specific parameters required to execute the tool from the user gogal.
    Please output the selected tool name and specific parameter information in json in the following required format, refer to the following example:
        user: Search for the latest hot financial news
        assisant: {{
          "tool_name":"The chart rendering method currently selected by SQL",
          "args": {{
            "query": "latest hot financial news",
          }},
          "thought":"I will use the google-search tool to search for the latest hot financial news."
        }}
      
      Please think step by step and return it in the following json format
      {{
          "tool_name":"The chart rendering method currently selected by SQL",
          "args": {{
            "arg name1": "arg value1",
            "arg name2": "arg value2",
          }},
          "thought":"Summary of thoughts to the user"
      }}
      Make sure the response is correct json and can be parsed by Python json.loads.
    """
    DEFAULT_DESCRIBE = """You can use the following tools to complete the task objectives, tool information: {tool-infos}"""
    NAME = "ToolScientist"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        plugin_path: str = None,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )

        self.register_reply(Agent, PluginAssistantAgent.a_tool_call)
        self.agent_context = agent_context
        self._plugin_loader = PluginLoader()
        if not plugin_path:
            plugin_path = PLUGINS_DIR
        self.plugin_generator = self._plugin_loader.load_plugins(
            plugin_path=plugin_path
        )

    async def a_system_fill_param(self):
        params = {
            "tool_list": self.plugin_generator.generate_commands_string(),
        }
        self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE.format(**params))

    async def a_tool_call(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code execution."""

        json_objects = find_json_objects(message)
        json_count = len(json_objects)

        rensponse_succ = True
        view = None
        tool_result = None
        err_msg = None
        if json_count != 1:
            ### Answer failed, turn on automatic repair
            rensponse_succ = False
            err_msg = "Your answer has multiple json contents, which is not the required return format."
        else:
            tool_name = json_objects[0].get("tool_name", None)
            args = json_objects[0].get("args", None)

            try:
                tool_result = execute_command(tool_name, args, self.plugin_generator)
                status = Status.COMPLETE.value
            except Exception as e:
                logger.exception(f"Tool [{tool_name}] excute Failed!")
                status = Status.FAILED.value
                err_msg = f"Tool [{tool_name}] excute Failed!{str(e)}"
                rensponse_succ = False

            plugin_param = {
                "name": tool_name,
                "args": args,
                "status": status,
                "logo": None,
                "result": tool_result,
                "err_msg": err_msg,
            }
            vis_tag = vis_client.get(VisPlugin.vis_tag())
            view = await vis_tag.disply(content=plugin_param)

        return True, {
            "is_exe_success": rensponse_succ,
            "content": tool_result if rensponse_succ else err_msg,
            "view": view,
        }
