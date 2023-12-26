import json
import logging
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from dbgpt.core.awel import BaseOperator
from dbgpt.util.json_utils import find_json_objects

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext
from ..base_agent import ConversableAgent

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x


logger = logging.getLogger(__name__)


class PluginAgent(ConversableAgent):
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
          "args": "{{
            "query": "latest hot financial news",
          }}",
          "thought":"I will use the google-search tool to search for the latest hot financial news."
        }}
      
      Please think step by step and return it in the following json format
      {{
          "tool_name":"The chart rendering method currently selected by SQL",
          "args": "{{
            "arg name1": "arg value1",
            "arg name2": "arg value2",
          }}",
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
        describe: Optional[str] = DEFAULT_DESCRIBE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )

        self.register_reply(Agent, PluginAgent.tool_call)
        self.agent_context = agent_context

    async def a_system_fill_param(self):
        params = {
            "tool_infos": self.db_connect.get_table_info(),
            "dialect": self.db_connect.db_type,
        }
        self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE.format(**params))

    async def tool_call(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code execution."""

        json_objects = find_json_objects(message)
        fail_reason = "The required json format answer was not generated."
        json_count = len(json_objects)
        rensponse_succ = True
        view = None
        content = None
        if json_count != 1:
            ### Answer failed, turn on automatic repair
            rensponse_succ = False
        else:
            try:
                view = ""
            except Exception as e:
                view = f"```vis-convert-error\n{content}\n```"

        return True, {
            "is_exe_success": rensponse_succ,
            "content": content,
            "view": view,
        }
