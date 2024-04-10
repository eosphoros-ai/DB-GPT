"""Agent Plans Vis Protocol."""
from ..base import Vis


class VisAgentPlans(Vis):
    """Agent Plans Vis Protocol."""

    @classmethod
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol module."""
        return "agent-plans"
