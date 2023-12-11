from collections import defaultdict
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from .agent import Agent
from .conversable_agent import ConversableAgent


def get_all_subclasses(cls):
    all_subclasses = []
    direct_subclasses = cls.__subclasses__()
    all_subclasses.extend(direct_subclasses)

    for subclass in direct_subclasses:
        all_subclasses.extend(get_all_subclasses(subclass))
    return all_subclasses

class AgentsMange:

    def __init__(self):
        self._agents= defaultdict()
        self._chat_group = None



    def init_agents(self):
        agent_cls = get_all_subclasses(ConversableAgent)
        for cls in agent_cls:
            self.register_agent(cls)

    def register_agent(self, cls):
        self._agents[cls.name] = cls


    def get_by_name(self, name:str)->Optional[Type[Agent]]:
        return self._agents[name]

    def all_agents(self):
        return self._agents.keys()