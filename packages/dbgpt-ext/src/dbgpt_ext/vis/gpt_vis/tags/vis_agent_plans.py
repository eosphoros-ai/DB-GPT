"""Viss Agent Plans."""

from dbgpt.vis import Vis


class VisAgentPlans(Vis):
    """VisAgentPlans."""

    @classmethod
    def vis_tag(cls):
        """Vis tag name.

        Returns:
            str: The tag name associated with the visualization.
        """
        return "agent-plans"
