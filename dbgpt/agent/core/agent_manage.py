"""Manages the registration and retrieval of agents."""

import logging
import re
from collections import defaultdict
from typing import Dict, List, Type

from ..expand.code_assistant_agent import CodeAssistantAgent
from ..expand.dashboard_assistant_agent import DashboardAssistantAgent
from ..expand.data_scientist_agent import DataScientistAgent
from ..expand.plugin_assistant_agent import PluginAssistantAgent
from ..expand.summary_assistant_agent import SummaryAssistantAgent
from .agent import Agent

logger = logging.getLogger(__name__)


def participant_roles(agents: List[Agent]) -> str:
    """Return a string listing the roles of the agents."""
    # Default to all agents registered
    roles = []
    for agent in agents:
        roles.append(f"{agent.get_name()}: {agent.get_describe()}")
    return "\n".join(roles)


def mentioned_agents(message_content: str, agents: List[Agent]) -> Dict:
    """Return a dictionary mapping agent names to mention counts.

    Finds and counts agent mentions in the string message_content, taking word
    boundaries into account.

    Returns: A dictionary mapping agent names to mention counts (to be included,
    at least one mention must occur)
    """
    mentions = dict()
    for agent in agents:
        regex = (
            r"(?<=\W)" + re.escape(agent.get_name()) + r"(?=\W)"
        )  # Finds agent mentions, taking word boundaries into account
        count = len(
            re.findall(regex, " " + message_content + " ")
        )  # Pad the message to help with matching
        if count > 0:
            mentions[agent.get_name()] = count
    return mentions


class AgentManager:
    """Manages the registration and retrieval of agents."""

    def __init__(self):
        """Create a new AgentManager."""
        self._agents = defaultdict()

    def register_agent(self, cls):
        """Register an agent."""
        self._agents[cls().profile] = cls

    def get_by_name(self, name: str) -> Type[Agent]:
        """Return an agent by name.

        Args:
            name (str): The name of the agent to retrieve.

        Returns:
            Type[Agent]: The agent with the given name.

        Raises:
            ValueError: If the agent with the given name is not registered.
        """
        if name not in self._agents:
            raise ValueError(f"Agent:{name} not register!")
        return self._agents[name]

    def get_describe_by_name(self, name: str) -> str:
        """Return the description of an agent by name."""
        return self._agents[name].desc

    def all_agents(self):
        """Return a dictionary of all registered agents and their descriptions."""
        result = {}
        for name, cls in self._agents.items():
            result[name] = cls.desc
        return result

    def list_agents(self):
        """Return a list of all registered agents and their descriptions."""
        result = []
        for name, cls in self._agents.items():
            instance = cls()
            result.append(
                {
                    "name": instance.profile,
                    "desc": instance.goal,
                }
            )
        return result


agent_manager = AgentManager()

agent_manager.register_agent(CodeAssistantAgent)
agent_manager.register_agent(DashboardAssistantAgent)
agent_manager.register_agent(DataScientistAgent)
agent_manager.register_agent(SummaryAssistantAgent)
agent_manager.register_agent(PluginAssistantAgent)
