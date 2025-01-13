"""Dashboard Assistant Agent."""

from typing import List, Optional

from ..core.agent import AgentMessage
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..resource.database import DBResource
from .actions.dashboard_action import DashboardAction


class DashboardAssistantAgent(ConversableAgent):
    """Dashboard Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Visionary",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "Reporter",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "Read the provided historical messages, collect various analysis SQLs "
            "from them, and assemble them into professional reports.",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "You are only responsible for collecting and sorting out the analysis "
                "SQL that already exists in historical messages, and do not generate "
                "any analysis sql yourself.",
                "In order to build a report with rich display types, you can "
                "appropriately adjust the display type of the charts you collect so "
                "that you can build a better report. Of course, you can choose from "
                "the following available display types: {{ display_type }}",
                "Please read and completely collect all analysis sql in the "
                "historical conversation, and do not omit or modify the content of "
                "the analysis sql.",
            ],
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Observe and organize various analysis results and construct "
            "professional reports",
            category="agent",
            key="dbgpt_agent_expand_dashboard_assistant_agent_profile_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new instance of DashboardAssistantAgent."""
        super().__init__(**kwargs)
        self._init_actions([DashboardAction])

    def _init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message, rely_messages)

        dbs: List[DBResource] = DBResource.from_resource(self.resource)

        if not dbs:
            raise ValueError(
                f"Resource type {self.actions[0].resource_need} is not supported."
            )
        db = dbs[0]
        reply_message.context = {
            "display_type": self.actions[0].render_prompt(),
            "dialect": db.dialect,
        }
        return reply_message
