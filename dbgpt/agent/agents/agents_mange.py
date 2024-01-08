from collections import defaultdict
from typing import Optional, Type

from .agent import Agent
from .expand.code_assistant_agent import CodeAssistantAgent
from .expand.dashboard_assistant_agent import DashboardAssistantAgent
from .expand.data_scientist_agent import DataScientistAgent
from .expand.sql_assistant_agent import SQLAssistantAgent


def get_all_subclasses(cls):
    all_subclasses = []
    direct_subclasses = cls.__subclasses__()
    all_subclasses.extend(direct_subclasses)

    for subclass in direct_subclasses:
        all_subclasses.extend(get_all_subclasses(subclass))
    return all_subclasses


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
