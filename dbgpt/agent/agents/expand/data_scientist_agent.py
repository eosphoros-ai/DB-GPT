from ..conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from ..agent import Agent
from ...memory.gpts_memory import GptsMemory
try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x
x

class DataScientistAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You are a helpful AI assistant who is good at writing SQL for various databases.
    Based on the given data structure information, and on the premise of satisfying the following constraints, use the correct {dialect} SQL to analyze and solve tasks.
    Data Structure information:
    {data_structure}
    Constraint:
    1.Please fully understand the user's problem and use duckdb sql for analysis. The analysis content is returned in the output format required below. Please output the sql in the corresponding sql parameter.
    2.Please choose the best one from the display methods given below for data rendering, and put the type name into the name parameter value that returns the required format. If you cannot find the most suitable one, use 'Table' as the display method. , the available data display methods are as follows: {disply_type}
    3.The table name that needs to be used in SQL is: {table_name}. Please check the sql you generated and do not use column names that are not in the data structure.
    4.Give priority to answering using data analysis. If the user's question does not involve data analysis, you can answer according to your understanding.
    5.The sql part of the output content is converted to: <api-call><name>[data display mode]</name><args><sql>[correct duckdb data analysis sql]</sql></args></api - call> For this format, please refer to the return format requirements.

    Please think step by step and give your answer, and make sure your answer is formatted as follows:
    thoughts summary to say to user.<api-call><name>[Data display method]</name><args><sql>[Correct duckdb data analysis sql]</sql></args></api-call>
    """

    def __init__(
            self,
            name: str,
            describe: Optional[str],
            memroy: GptsMemory,
            llm_config: Optional[Union[Dict, Literal[False]]] = None,
            is_termination_msg: Optional[Callable[[Dict], bool]] = None,
            max_consecutive_auto_reply: Optional[int] = None,
            human_input_mode: Optional[str] = "NEVER",
            agent_context: 'AgentContext' = None,
            **kwargs,
    ):
        super().__init__(
            name,
            memroy,
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
            DataScientistAgent.generate_analysis_chart_reply
        )
        self.agent_context = agent_context
        self.db_connect = CFG.LOCAL_DB_MANAGE.get_connect(self.agent_context.db_name)

    async def a_receive(self, message: Union[Dict, str], sender: Agent, reviewer: "Agent",
                        request_reply: Optional[bool] = None, silent: Optional[bool] = False,
                        is_plan_goals: Optional[bool] = False):
        ### If it is a message sent to yourself, go to repair sytem prompt
        params = {
            "data_structure": self.db_connect.get_table_info(),
            "disply_type": ApiCall.default_chart_type_promot(),
            "dialect": self.db_connect.db_type
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
        self.api_call = ApiCall(display_registry=[])
        if self.api_call.check_have_plugin_call(message):
            exit_success = True
            try:
                chart_vis = self.api_call.display_sql_llmvis(message, self.db_connect.run_to_df)
            except Exception as e:
                err_info = f"{str(e)}"
                exit_success = False
            output = chart_vis if exit_success else err_info
        else:
            exit_success = False
            output = message

        return True, {"is_exe_success": exit_success,
                      "content": f"{output}"}
