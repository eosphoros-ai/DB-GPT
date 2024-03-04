import json
from typing import Callable, Dict, List, Literal, Optional, Union

from dbgpt.agent.actions.dashboard_action import DashboardAction
from dbgpt.agent.plugin.commands.command_mange import ApiCall
from dbgpt.util.json_utils import find_json_objects

from ...memory.gpts_memory import GptsMemory
from ..base_agent_new import ConversableAgent


class DashboardAssistantAgent(ConversableAgent):
    name: str = "Visionary"  # Chartwell

    profile: str = "Reporter"
    goal: str = "Read the provided historical messages, collect various analysis SQLs from them, and assemble them into professional reports."
    constraints: List[str] = [
        "You are only responsible for collecting and sorting out the analysis SQL that already exists in historical messages, and do not generate any analysis sql yourself.",
        "In order to build a report with rich display types, you can appropriately adjust the display type of the charts you collect so that you can build a better report. Of course, you can choose from the following available display types: {display_type}",
        "Please read and completely collect all analysis sql in the historical conversation, and do not omit or modify the content of the analysis sql.",
    ]
    desc: str = "Observe and organize various analysis results and construct professional reports"

    max_retry_count: int = 3

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([DashboardAction])

    def _init_reply_message(self, recive_message):
        reply_message = super()._init_reply_message(recive_message)
        reply_message["context"] = {
            "display_type": self.actions[0].render_prompt(),
            "dialect": self.resource_loader.get_resesource_api(
                self.actions[0].resource_need
            ).get_data_type(self.resources[0]),
        }
        return reply_message
