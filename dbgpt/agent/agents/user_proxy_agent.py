from typing import Callable, Dict, List, Literal, Optional, Tuple, Union

from ..memory.gpts_memory import GptsMemory
from .agent import Agent, AgentContext
from .base_agent_new import ConversableAgent


class UserProxyAgent(ConversableAgent):
    """(In preview) A proxy agent for the user, that can execute code and provide feedback to the other agents."""

    name = "User"
    profile: str = "Human"

    desc: str = (
        "A human admin. Interact with the planner to discuss the plan. Plan execution needs to be approved by this admin.",
    )

    is_human = True
