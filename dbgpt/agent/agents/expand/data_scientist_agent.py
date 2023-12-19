import json

from ..conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
import logging
from ..agent import Agent
from ...memory.gpts_memory import GptsMemory
from dbgpt._private.config import Config
from dbgpt.agent.commands.command_mange import ApiCall
from dbgpt.util.json_utils import find_json_objects

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x

CFG = Config()
logger = logging.getLogger(__name__)


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
    1.Please choose the best one from the display methods given below for data rendering, and put the type name into the name parameter value that returns the required format. If you cannot find the most suitable one, use 'Table' as the display method. , the available data display methods are as follows: {disply_type}
    2.Please check the sql you generated, do not use column names that do not exist in the data structure, and do not make mistakes in the relationship between column names and tables.
    3.Pay attention to the data association between tables, which can be analyzed through joint query and analysis of multiple tables.
    Please think step by step and return in the following json format
    {{
        "display_type":"The chart rendering method selected for the current sql",
        "sql": "Analysis sql of the current step task",
        "thought":"thoughts summary to say to user"
    }}
    Ensure the response is correct json and can be parsed by Python json.loads.
    """
    DEFAULT_DESCRIBE = """Using the local database, it is possible to generate analysis SQL to obtain data based on the table structure, and at the same time generate visual charts of the corresponding data. """
    NAME = "DataScientist"

    def __init__(
            self,
            memory: GptsMemory,
            agent_context: 'AgentContext',
            model_priority: Optional[List[str]] = None,
            describe: Optional[str] = DEFAULT_DESCRIBE,
            is_termination_msg: Optional[Callable[[Dict], bool]] = None,
            max_consecutive_auto_reply: Optional[int] = None,
            human_input_mode: Optional[str] = "NEVER",

            **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            model_priority=model_priority,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )

        self.register_reply(
            Agent,
            DataScientistAgent.generate_analysis_chart_reply
        )
        self.agent_context = agent_context
        self.db_connect = CFG.LOCAL_DB_MANAGE.get_connect(self.agent_context.resource_db.get('name', None))

    async def a_receive(self, message: Union[Dict, str], sender: Agent, reviewer: "Agent",
                        request_reply: Optional[bool] = None, silent: Optional[bool] = False):
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
            config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code execution."""

        json_objects = find_json_objects(message)
        fail_reason = "Please recheck your answer，no usable analyze sql generated in correct format，"
        json_count = len(json_objects)
        rensponse_succ = True
        if json_count != 1:
            ### Answer failed, turn on automatic repair
            fail_reason += f"There are currently {json_count} json contents"
            rensponse_succ = False
        else:
            content = json.dumps(json_objects[0])
        if not rensponse_succ:
            content = fail_reason
        return True, {"is_exe_success": rensponse_succ, "content": content}



    async def a_verify_reply(self, action_reply: Optional[Dict], sender: "Agent", **kwargs):
        if  action_reply.get("is_exe_success", False) ==False:
            return False, f"Please check your answer, Execution failed, error reason:{action_reply.get('content', '')}."
        action_reply_obj =  json.loads(action_reply.get('content', ''))
        sql = action_reply_obj.get("sql", None)
        if not sql:
            return False, "Please check your answer, the sql information that needs to be generated is not found."
        try:
            columns, values = self.db_connect.query_ex(sql)
            if not values or len(values)<=0:
                return False, "Please check your answer, the generated SQL cannot query any data."
            else:
                logger.info(f"reply check success! There are {len(values)} rows of data")
                return True, None
        except Exception as e:
            return False, f"Please check your answer. The generated SQL check fails and has the following error:{str(e)}"

