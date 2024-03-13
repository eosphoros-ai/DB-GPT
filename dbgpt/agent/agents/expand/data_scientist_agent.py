import json
import logging
from typing import Callable, Dict, List, Literal, Optional, Union

from dbgpt.agent.actions.action import ActionOutput
from dbgpt.agent.actions.chart_action import ChartAction
from dbgpt.agent.resource.resource_api import ResourceType
from dbgpt.agent.resource.resource_db_api import ResourceDbClient

from ..base_agent_new import ConversableAgent

logger = logging.getLogger(__name__)


class DataScientistAgent(ConversableAgent):
    name = "Edgar"
    profile: str = "DataScientist"
    goal: str = "Use correct {dialect} SQL to analyze and solve tasks based on the data structure information of the database given in the resource."
    constraints: List[str] = [
        "Please check the generated SQL carefully. Please strictly abide by the data structure definition given. It is prohibited to use non-existent fields and data values. Do not use fields from table A to table B. You can perform multi-table related queries.",
        "If the data and fields that need to be analyzed in the target are in different tables, it is recommended to use multi-table correlation queries first, and pay attention to the correlation between multiple table structures.",
        "It is forbidden to construct data by yourself as a query condition. If you want to query a specific field, if the value of the field is provided, then you can perform a group statistical query on the field.",
        "Please select an appropriate one from the supported display methods for data display. If no suitable display type is found, table display is used by default. Supported display types: \n {display_type}",
    ]
    desc: str = "Use database resources to conduct data analysis, analyze SQL, and provide recommended rendering methods."
    max_retry_count: int = 5

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([ChartAction])

    def _init_reply_message(self, recive_message):
        reply_message = super()._init_reply_message(recive_message)
        reply_message["context"] = {
            "display_type": self.actions[0].render_prompt(),
            "dialect": self.resource_loader.get_resesource_api(
                self.actions[0].resource_need
            ).get_data_type(self.resources[0]),
        }
        return reply_message

    async def a_correctness_check(self, message: Optional[Dict]):
        action_reply = message.get("action_report", None)
        if action_reply is None:
            return (
                False,
                f"No executable analysis SQL is generated,{message['content']}.",
            )
        action_out = ActionOutput.from_dict(action_reply)
        if action_out.is_exe_success == False:
            return (
                False,
                f"Please check your answer, {action_out.content}.",
            )
        action_reply_obj = json.loads(action_out.content)
        sql = action_reply_obj.get("sql", None)
        if not sql:
            return (
                False,
                "Please check your answer, the sql information that needs to be generated is not found.",
            )
        try:
            resource_db_client: ResourceDbClient = (
                self.resource_loader.get_resesource_api(
                    ResourceType(action_out.resource_type)
                )
            )

            columns, values = await resource_db_client.a_query(
                db=action_out.resource_value, sql=sql
            )
            if not values or len(values) <= 0:
                return (
                    False,
                    "Please check your answer, the current SQL cannot find the data to determine whether filtered field values or inappropriate filter conditions are used.",
                )
            else:
                logger.info(
                    f"reply check success! There are {len(values)} rows of data"
                )
                return True, None
        except Exception as e:
            logger.exception(f"DataScientist check exception！{str(e)}")
            return (
                False,
                f"SQL execution error, please re-read the historical information to fix this SQL. The error message is as follows:{str(e)}",
            )
