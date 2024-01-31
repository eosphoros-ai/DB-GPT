import json
from typing import Callable, Dict, List, Literal, Optional, Union

from dbgpt._private.config import Config
from dbgpt.agent.actions.dashboard_action import DashboardAction
from dbgpt.agent.plugin.commands.command_mange import ApiCall
from dbgpt.util.json_utils import find_json_objects

from ...memory.gpts_memory import GptsMemory
from ..base_agent_new import ConversableAgent

# TODO: remove global config
CFG = Config()


class DashboardAssistantAgent(ConversableAgent):
    name: str = "Visionary"  # Chartwell

    profile: str = "Reporter"
    goal: str = "Read the provided historical messages, collect various analysis SQLs from them, and assemble them into professional reports."
    constraints: List[str] = [
        "You are only responsible for collecting and sorting out the analysis SQL that already exists in historical messages, and do not generate any analysis content yourself.",
        "If the analysis SQL in historical messages does not provide a corresponding chart type, you can select an appropriate display type from the following available display types:{disply_type}",
    ]
    desc: str = "Observe and organize various analysis results and construct professional reports"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([DashboardAction])

    def _init_reply_message(self, recive_message):
        reply_message = super()._init_reply_message(recive_message)
        reply_message["context"] = {
            "disply_type": self.actions[0].render_prompt(),
            "dialect": self.resource_loader.get_resesource_api(
                self.actions[0].resource_need
            ).get_data_type(self.resources[0]),
        }
        return reply_message
