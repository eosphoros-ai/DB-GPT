from typing import Callable, Dict, Literal, Optional, Union

from dbgpt._private.config import Config
from dbgpt.agent.agents.base_agent import ConversableAgent
from dbgpt.agent.plugin.commands.command_mange import ApiCall

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext

# TODO: remove global config
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

    DEFAULT_DESCRIBE = """You can analyze data with a known structure through SQL and generate a single analysis chart for a given target. Please note that you do not have the ability to obtain and process data and can only perform data analysis based on a given structure. If the task goal cannot or does not need to be solved by SQL analysis, please do not use"""

    NAME = "SqlEngineer"

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
        self.register_reply(Agent, SQLAssistantAgent.generate_analysis_chart_reply)
        self.agent_context = agent_context
        self.db_connect = CFG.LOCAL_DB_MANAGE.get_connect(
            self.agent_context.resource_db.get("name", None)
        )

    async def a_system_fill_param(self):
        params = {
            "data_structure": self.db_connect.get_table_info(),
            "disply_type": ApiCall.default_chart_type_promot(),
            "dialect": self.db_connect.db_type,
        }
        self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE.format(**params))

    async def generate_analysis_chart_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
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
                chart_vis = self.api_call.display_sql_llmvis(
                    message, self.db_connect.run_to_df
                )
            except Exception as e:
                err_info = f"{str(e)}"
                exit_success = False
            output = chart_vis if exit_success else err_info
        else:
            exit_success = False
            output = message

        return True, {"is_exe_success": exit_success, "content": f"{output}"}
