from ..conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from ..agent import Agent
from ...memory.gpts_memory import GptsMemory
from ...commands.command_mange import ApiCall

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x
from dbgpt._private.config import Config

CFG = Config()


class SQLAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You are a SQL expert and answer user questions by writing SQL using the following data structures.
    Use the following data structure to write the best mysql SQL for the user's problem. 
    Data Structure information:
    {data_structure}
    
    - Please ensure that the SQL is correct and high-performance.
    - Please be careful not to use tables or fields that are not mentioned.
    - Make sure to only return SQL.
    """

    def __init__(
            self,
            name: str,
            describe: Optional[str],
            memory: GptsMemory,
            is_termination_msg: Optional[Callable[[Dict], bool]] = None,
            max_consecutive_auto_reply: Optional[int] = None,
            human_input_mode: Optional[str] = "NEVER",
            agent_context: 'AgentContext' = None,
            **kwargs,
    ):
        super().__init__(
            name,
            memory,
            describe,
            self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg,
            max_consecutive_auto_reply,
            human_input_mode,
            agent_context,
            **kwargs,
        )

        self.register_reply(
            Agent,
            SQLAssistantAgent.generate_analysis_chart_reply
        )
        self.agent_context = agent_context
        self.db_connect = CFG.LOCAL_DB_MANAGE.get_connect(self.agent_context.db_name)

    async def a_receive(self, message: Union[Dict, str], sender: Agent, reviewer: "Agent",
                        request_reply: Optional[bool] = None, silent: Optional[bool] = False,  is_plan_goals: Optional[bool] = False):
        ### If it is a message sent to yourself, go to repair sytem prompt
        params = {
            "data_structure": self.agent_context.resources['db'],
            "disply_type": ApiCall.default_chart_type_promot(),
        }
        self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE.format(**params))
        return await super().a_receive(message, sender, reviewer, request_reply, silent)


    async def generate_analysis_chart_reply(
            self,
            message: Optional[str] = None,
            sender: Optional[Agent] = None,
            reviewer: "Agent" = None,
            is_plan_goals: Optional[bool] = False,
            config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code execution."""

        # iterate through the last n messages reversly
        # if code blocks are found, execute the code blocks and return the output
        # if no code blocks are found, continue

        self.api_call = ApiCall(display_registry=[])
        if self.api_call.check_have_plugin_call(message):
            exit_success = True
            try:
                chart_vis = self.api_call.display_sql_llmvis(message, self.db_connect.run_to_df)
            except Exception as e:
                err_info = f"{str(e)}"
                exit_success = False
            output = chart_vis if exit_success else  err_info
        else:
            exit_success = False
            output = message

        return True, {"is_exe_success": exit_success,
                      "content": f"{output}"}
