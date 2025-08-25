"""Viss Agent Plans."""

import json

from dbgpt.util.json_utils import serialize
from dbgpt.vis.base import Vis


class VisAgentTabs(Vis):
    """VisAgentPlans."""

    def sync_display(self, **kwargs) -> str:
        """Display the content using the vis protocol."""
        content = kwargs.get("content")
        try:
            content = json.dumps(
                self.sync_generate_param(**kwargs),
                default=serialize,
                ensure_ascii=False,
            )
            return f"```{self.vis_tag()}\n{content}\n```"
        except Exception:
            return f"```{self.vis_tag()}\n{content}\n```"

    @classmethod
    def vis_tag(cls):
        """Vis tag name.

        Returns:
            str: The tag name associated with the visualization.
        """
        return "vis-tabs"
