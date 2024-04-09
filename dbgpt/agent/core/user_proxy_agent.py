"""A proxy agent for the user."""
from .base_agent import ConversableAgent


class UserProxyAgent(ConversableAgent):
    """A proxy agent for the user.

    That can execute code and provide feedback to the other agents.
    """

    name = "User"
    profile: str = "Human"

    desc: str = (
        "A human admin. Interact with the planner to discuss the plan. "
        "Plan execution needs to be approved by this admin."
    )

    is_human = True
