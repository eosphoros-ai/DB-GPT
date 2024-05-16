"""Data Scientist Agent."""

import json
import logging
from typing import List, Optional, Tuple, cast

from ..core.action.base import ActionOutput
from ..core.agent import AgentMessage
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..resource.database import DBResource
from .actions.chart_action import ChartAction

logger = logging.getLogger(__name__)


class DataScientistAgent(ConversableAgent):
    """Data Scientist Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Edgar",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "DataScientist",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "Use correct {{ dialect }} SQL to analyze and solve tasks based on the data"
            " structure information of the database given in the resource.",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Please check the generated SQL carefully. Please strictly abide by "
                "the data structure definition given. It is prohibited to use "
                "non-existent fields and data values. Do not use fields from table A "
                "to table B. You can perform multi-table related queries.",
                "If the data and fields that need to be analyzed in the target are in "
                "different tables, it is recommended to use multi-table correlation "
                "queries first, and pay attention to the correlation between multiple "
                "table structures.",
                "It is forbidden to construct data by yourself as a query condition. "
                "If you want to query a specific field, if the value of the field is "
                "provided, then you can perform a group statistical query on the "
                "field.",
                "Please select an appropriate one from the supported display methods "
                "for data display. If no suitable display type is found, "
                "table display is used by default. Supported display types: \n"
                "{{ display_type }}",
            ],
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Use database resources to conduct data analysis, analyze SQL, and provide "
            "recommended rendering methods.",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_desc",
        ),
    )

    max_retry_count: int = 5

    def __init__(self, **kwargs):
        """Create a new DataScientistAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([ChartAction])

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        reply_message.context = {
            "display_type": self.actions[0].render_prompt(),
            "dialect": self.database.dialect,
        }
        return reply_message

    @property
    def database(self) -> DBResource:
        """Get the database resource."""
        dbs: List[DBResource] = DBResource.from_resource(self.resource)
        if not dbs:
            raise ValueError(
                f"Resource type {self.actions[0].resource_need} is not supported."
            )
        return dbs[0]

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Verify whether the current execution results meet the target expectations."""
        action_reply = message.action_report
        if action_reply is None:
            return (
                False,
                f"No executable analysis SQL is generated,{message.content}.",
            )
        action_out = cast(ActionOutput, ActionOutput.from_dict(action_reply))
        if not action_out.is_exe_success:
            return (
                False,
                f"Please check your answer, {action_out.content}.",
            )
        action_reply_obj = json.loads(action_out.content)
        sql = action_reply_obj.get("sql", None)
        if not sql:
            return (
                False,
                "Please check your answer, the sql information that needs to be "
                "generated is not found.",
            )
        try:
            if not action_out.resource_value:
                return (
                    False,
                    "Please check your answer, the data resource information is not "
                    "found.",
                )

            columns, values = await self.database.query(
                sql=sql,
                db=action_out.resource_value,
            )
            if not values or len(values) <= 0:
                return (
                    False,
                    "Please check your answer, the current SQL cannot find the data to "
                    "determine whether filtered field values or inappropriate filter "
                    "conditions are used.",
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
                f"SQL execution error, please re-read the historical information to "
                f"fix this SQL. The error message is as follows:{str(e)}",
            )
