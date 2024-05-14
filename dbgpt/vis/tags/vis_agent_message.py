"""Protocol module for agent messages vis tag."""
from ..base import Vis


class VisAgentMessages(Vis):
    """Agent Messages Vis Protocol."""

    @classmethod
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol module."""
        return "agent-messages"
