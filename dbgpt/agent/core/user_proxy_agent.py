"""A proxy agent for the user."""
from .base_agent import ConversableAgent
from .profile import ProfileConfig


class UserProxyAgent(ConversableAgent):
    """A proxy agent for the user.

    That can execute code and provide feedback to the other agents.
    """

    profile: ProfileConfig = ProfileConfig(
        name="User",
        role="Human",
        description=(
            "A human admin. Interact with the planner to discuss the plan. "
            "Plan execution needs to be approved by this admin."
        ),
    )

    is_human: bool = True
