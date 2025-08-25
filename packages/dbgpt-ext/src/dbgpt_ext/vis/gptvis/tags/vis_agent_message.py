"""Vis Agent Messages."""

from dbgpt.vis.base import Vis


class VisAgentMessages(Vis):
    """Vis Agent Messages."""

    @classmethod
    def vis_tag(cls):
        """Vis tag name."""
        return "agent-messages"
