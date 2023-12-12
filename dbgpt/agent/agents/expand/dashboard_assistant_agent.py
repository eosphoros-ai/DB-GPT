from ..conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from ..agent import Agent
from ...memory.gpts_memory import GptsMemory



try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x




class DashboardAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You are an analytical reporting expert. Please collect and organize the completed analysis data chart results and output a complete analysis report.
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
            DashboardAssistantAgent.generate_dashboard_reply
        )
        self.agent_context = agent_context


    async def a_receive(self, message: Union[Dict, str], sender: Agent, reviewer: "Agent",
                        request_reply: Optional[bool] = None, silent: Optional[bool] = False,  is_plan_goals: Optional[bool] = False):
        ### If it is a message sent to yourself, go to repair sytem prompt
        # params = {
        #     "data_structure": self.agent_context.resources['db'],
        #     "disply_type": ApiCall.default_chart_type_promot(),
        # }
        # self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE.format(**params))
        return await super().a_receive(message, sender, reviewer, request_reply, silent)


    async def generate_dashboard_reply(
            self,
            message: Optional[str] = None,
            sender: Optional[Agent] = None,
            reviewer: "Agent" = None,
            is_plan_goals: Optional[bool] = False,
            config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code execution."""

        exit_success = True
        try:
            dashbord_out = "http://xxx.123.com/123/test" #TODO
        except Exception as e:
            err_info = f"{str(e)}"
            exit_success = False
        output = dashbord_out if exit_success else  err_info


        return True, {"is_exe_success": exit_success,
                      "content": f"{output}"}
