import json
import logging
from typing import Callable, Dict, Literal, Optional, Union

from dbgpt._private.config import Config
from dbgpt.agent.plugin.commands.command_mange import ApiCall
from dbgpt.util.json_utils import find_json_objects

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext
from ..base_agent import ConversableAgent

# TODO: remove global config
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
      Based on the given data structure information, use the correct {dialect} SQL to analyze and solve the task, subject to the following constraints.
      Data structure information:
      {data_structure}
      constraint:
      1. Please choose the best one from the display methods given below for data display, and put the type name into the name parameter value that returns the required format. If you can't find the most suitable display method, use Table as the display method. , the available data display methods are as follows: {disply_type}
      2. Please check the sql you generated. It is forbidden to use column names that do not exist in the table, and it is forbidden to make up fields and tables that do not exist.
      3. Pay attention to the data association between tables and tables, and you can use multiple tables at the same time to generate a SQL.
      Please think step by step and return it in the following json format
      {{
          "display_type":"The chart rendering method currently selected by SQL",
          "sql": "Analysis sql of the current step task",
          "thought":"Summary of thoughts to the user"
      }}
      Make sure the response is correct json and can be parsed by Python json.loads.
    """
    DEFAULT_DESCRIBE = """It is possible use the local database to generate analysis SQL to obtain data based on the table structure, and at the same time generate visual charts of the corresponding data. Note that only local databases can be queried."""
    NAME = "DataScientist"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
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

        self.register_reply(Agent, DataScientistAgent.generate_analysis_chart_reply)
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

        json_objects = find_json_objects(message)
        fail_reason = "The required json format answer was not generated."
        json_count = len(json_objects)
        response_success = True
        view = None
        content = None
        if json_count != 1:
            # Answer failed, turn on automatic repair
            response_success = False
        else:
            try:
                content = json.dumps(json_objects[0], ensure_ascii=False)
            except Exception as e:
                fail_reason = (
                    f"There is a format problem with the json of the answer，{str(e)}"
                )
                response_success = False
            try:
                vis_client = ApiCall()
                view = vis_client.display_only_sql_vis(
                    json_objects[0], self.db_connect.run_to_df
                )
            except Exception as e:
                view = f"```vis-convert-error\n{content}\n```"

        return True, {
            "is_exe_success": response_success,
            "content": content if response_success else fail_reason,
            "view": view,
        }

    async def a_verify(self, message: Optional[Dict]):
        action_reply = message.get("action_report", None)
        # TODO None has no method get
        if action_reply.get("is_exe_success", False) == False:
            return (
                False,
                f"Please check your answer, {action_reply.get('content', '')}.",
            )
        action_reply_obj = json.loads(action_reply.get("content", ""))
        sql = action_reply_obj.get("sql", None)
        if not sql:
            return (
                False,
                "Please check your answer, the sql information that needs to be generated is not found.",
            )
        try:
            columns, values = self.db_connect.query_ex(sql)
            if not values or len(values) <= 0:
                return (
                    False,
                    "Please check your answer, the generated SQL cannot query any data.",
                )
            else:
                logger.info(
                    f"reply check success! There are {len(values)} rows of data"
                )
                return True, None
        except Exception as e:
            return (
                False,
                f"SQL execution error, please re-read the historical information to fix this SQL. The error message is as follows:{str(e)}",
            )
