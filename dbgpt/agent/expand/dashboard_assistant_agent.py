"""Dashboard Assistant Agent."""

from typing import List

from ..actions.dashboard_action import DashboardAction
from ..core.agent import AgentMessage
from ..core.base_agent import ConversableAgent
from ..resource.resource_db_api import ResourceDbClient


class DashboardAssistantAgent(ConversableAgent):
    """Dashboard Assistant Agent."""

    name: str = "Visionary"

    profile: str = "Reporter"
    goal: str = (
        "Read the provided historical messages, collect various analysis SQLs "
        "from them, and assemble them into professional reports."
    )
    constraints: List[str] = [
        "You are only responsible for collecting and sorting out the analysis SQL that"
        " already exists in historical messages, and do not generate any analysis sql "
        "yourself.",
        "In order to build a report with rich display types, you can appropriately "
        "adjust the display type of the charts you collect so that you can build a "
        "better report. Of course, you can choose from the following available "
        "display types: {display_type}",
        "Please read and completely collect all analysis sql in the historical "
        "conversation, and do not omit or modify the content of the analysis sql.",
    ]
    desc: str = (
        "Observe and organize various analysis results and construct "
        "professional reports"
    )

    max_retry_count: int = 3

    def __init__(self, **kwargs):
        """Create a new instance of DashboardAssistantAgent."""
        super().__init__(**kwargs)
        self._init_actions([DashboardAction])

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        client = self.not_null_resource_loader.get_resource_api(
            self.actions[0].resource_need, ResourceDbClient
        )
        if not client:
            raise ValueError(
                f"Resource type {self.actions[0].resource_need} is not supported."
            )
        reply_message.context = {
            "display_type": self.actions[0].render_prompt(),
            "dialect": client.get_data_type(self.resources[0]),
        }
        return reply_message
