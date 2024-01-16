import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Type

from .agent import Agent
from .expand.code_assistant_agent import CodeAssistantAgent
from .expand.dashboard_assistant_agent import DashboardAssistantAgent
from .expand.data_scientist_agent import DataScientistAgent
from .expand.plugin_assistant_agent import PluginAssistantAgent
from .expand.sql_assistant_agent import SQLAssistantAgent
from .expand.summary_assistant_agent import SummaryAssistantAgent
from .expand.retrieve_summary_assistant_agent import RetrieveSummaryAssistantAgent

logger = logging.getLogger(__name__)


def get_all_subclasses(cls):
    all_subclasses = []
    direct_subclasses = cls.__subclasses__()
    all_subclasses.extend(direct_subclasses)

    for subclass in direct_subclasses:
        all_subclasses.extend(get_all_subclasses(subclass))
    return all_subclasses


def participant_roles(agents: List[Agent] = None) -> str:
    # Default to all agents registered
    if agents is None:
        agents = agents

    roles = []
    for agent in agents:
        if agent.system_message.strip() == "":
            logger.warning(
                f"The agent '{agent.name}' has an empty system_message, and may not work well with GroupChat."
            )
        roles.append(f"{agent.name}: {agent.describe}")
    return "\n".join(roles)


def mentioned_agents(message_content: str, agents: List[Agent]) -> Dict:
    """
    Finds and counts agent mentions in the string message_content, taking word boundaries into account.

    Returns: A dictionary mapping agent names to mention counts (to be included, at least one mention must occur)
    """
    mentions = dict()
    for agent in agents:
        regex = (
            r"(?<=\W)" + re.escape(agent.name) + r"(?=\W)"
        )  # Finds agent mentions, taking word boundaries into account
        count = len(
            re.findall(regex, " " + message_content + " ")
        )  # Pad the message to help with matching
        if count > 0:
            mentions[agent.name] = count
    return mentions


class AgentsMange:
    def __init__(self):
        self._agents = defaultdict()

    def register_agent(self, cls):
        self._agents[cls.NAME] = cls

    def get_by_name(self, name: str) -> Optional[Type[Agent]]:
        if name not in self._agents:
            raise ValueError(f"Agent:{name} not register!")
        return self._agents[name]

    def get_describe_by_name(self, name: str) -> Optional[Type[Agent]]:
        return self._agents[name].DEFAULT_DESCRIBE

    def all_agents(self):
        result = {}
        for name, cls in self._agents.items():
            result[name] = cls.DEFAULT_DESCRIBE
        return result


agent_mange = AgentsMange()

agent_mange.register_agent(CodeAssistantAgent)
agent_mange.register_agent(DashboardAssistantAgent)
agent_mange.register_agent(DataScientistAgent)
agent_mange.register_agent(SQLAssistantAgent)
agent_mange.register_agent(SummaryAssistantAgent)
agent_mange.register_agent(PluginAssistantAgent)
agent_mange.register_agent(RetrieveSummaryAssistantAgent)
