"""Manages the registration and retrieval of agents."""

import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Type, cast

from dbgpt.component import BaseComponent, ComponentType, SystemApp

from ..expand.Indicator_assistant_agent import IndicatorAssistantAgent
from ..expand.simple_assistant_agent import SimpleAssistantAgent
from .agent import Agent
from .base_agent import ConversableAgent

logger = logging.getLogger(__name__)


def participant_roles(agents: List[Agent]) -> str:
    """Return a string listing the roles of the agents."""
    # Default to all agents registered
    roles = []
    for agent in agents:
        roles.append(f"{agent.name}: {agent.desc}")
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
            r"(?<=\W)" + re.escape(agent.name) + r"(?=\W)"
        )  # Finds agent mentions, taking word boundaries into account
        count = len(
            re.findall(regex, " " + message_content + " ")
        )  # Pad the message to help with matching
        if count > 0:
            mentions[agent.name] = count
    return mentions


class AgentManager(BaseComponent):
    """Manages the registration and retrieval of agents."""

    name = ComponentType.AGENT_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new AgentManager."""
        super().__init__(system_app)
        self.system_app = system_app
        self._agents: Dict[str, Tuple[Type[ConversableAgent], ConversableAgent]] = (
            defaultdict()
        )

        self._core_agents: Set[str] = set()

    def init_app(self, system_app: SystemApp):
        """Initialize the AgentManager."""
        self.system_app = system_app

    def after_start(self):
        """Register all agents."""
        from ..expand.code_assistant_agent import CodeAssistantAgent
        from ..expand.dashboard_assistant_agent import DashboardAssistantAgent
        from ..expand.data_scientist_agent import DataScientistAgent
        from ..expand.summary_assistant_agent import SummaryAssistantAgent
        from ..expand.tool_assistant_agent import ToolAssistantAgent

        core_agents = set()
        core_agents.add(self.register_agent(CodeAssistantAgent))
        core_agents.add(self.register_agent(DashboardAssistantAgent))
        core_agents.add(self.register_agent(DataScientistAgent))
        core_agents.add(self.register_agent(SummaryAssistantAgent))
        core_agents.add(self.register_agent(ToolAssistantAgent))
        core_agents.add(self.register_agent(IndicatorAssistantAgent))
        core_agents.add(self.register_agent(SimpleAssistantAgent))

        self._core_agents = core_agents

    def register_agent(
        self, cls: Type[ConversableAgent], ignore_duplicate: bool = False
    ) -> str:
        """Register an agent."""
        inst = cls()
        profile = inst.role
        if profile in self._agents and (
            profile in self._core_agents or not ignore_duplicate
        ):
            raise ValueError(f"Agent:{profile} already register!")
        self._agents[profile] = (cls, inst)
        return profile

    def get_by_name(self, name: str) -> Type[ConversableAgent]:
        """Return an agent by name.

        Args:
            name (str): The name of the agent to retrieve.

        Returns:
            Type[ConversableAgent]: The agent with the given name.

        Raises:
            ValueError: If the agent with the given name is not registered.
        """
        if name not in self._agents:
            raise ValueError(f"Agent:{name} not register!")
        return self._agents[name][0]

    def get_describe_by_name(self, name: str) -> str:
        """Return the description of an agent by name."""
        return self._agents[name][1].desc or ""

    def all_agents(self) -> Dict[str, str]:
        """Return a dictionary of all registered agents and their descriptions."""
        result = {}
        for name, value in self._agents.items():
            result[name] = value[1].desc or ""
        return result

    def list_agents(self):
        """Return a list of all registered agents and their descriptions."""
        result = []
        for name, value in self._agents.items():
            result.append(
                {
                    "name": value[1].role,
                    "desc": value[1].goal,
                }
            )
        return result


_SYSTEM_APP: Optional[SystemApp] = None


def initialize_agent(system_app: SystemApp):
    """Initialize the agent manager."""
    global _SYSTEM_APP
    _SYSTEM_APP = system_app
    agent_manager = AgentManager(system_app)
    system_app.register_instance(agent_manager)


def get_agent_manager(system_app: Optional[SystemApp] = None) -> AgentManager:
    """Return the agent manager.

    Args:
        system_app (Optional[SystemApp], optional): The system app. Defaults to None.

    Returns:
        AgentManager: The agent manager.
    """
    if not _SYSTEM_APP:
        if not system_app:
            system_app = SystemApp()
        initialize_agent(system_app)
    app = system_app or _SYSTEM_APP
    return AgentManager.get_instance(cast(SystemApp, app))
