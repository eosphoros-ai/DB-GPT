"""Client for vis protocol."""

from typing import Dict, Type

from .base import Vis
from .tags.vis_agent_message import VisAgentMessages
from .tags.vis_agent_plans import VisAgentPlans
from .tags.vis_api_response import VisApiResponse
from .tags.vis_app_link import VisAppLink
from .tags.vis_chart import VisChart
from .tags.vis_code import VisCode
from .tags.vis_dashboard import VisDashboard
from .tags.vis_plugin import VisPlugin
from .tags.vis_thinking import VisThinking


class VisClient:
    """Client for vis protocol."""

    def __init__(self):
        """Client for vis protocol."""
        self._vis_tag: Dict[str, Vis] = {}

    def register(self, vis_cls: Type[Vis]):
        """Register the vis protocol."""
        self._vis_tag[vis_cls.vis_tag()] = vis_cls()

    def get(self, tag_name):
        """Get the vis protocol by tag name."""
        if tag_name not in self._vis_tag:
            raise ValueError(f"Vis protocol tags not yet supported！[{tag_name}]")
        return self._vis_tag[tag_name]

    def tag_names(self):
        """Return the tag names of the vis protocol."""
        self._vis_tag.keys()


vis_client = VisClient()

vis_client.register(VisCode)
vis_client.register(VisChart)
vis_client.register(VisDashboard)
vis_client.register(VisAgentPlans)
vis_client.register(VisAgentMessages)
vis_client.register(VisPlugin)
vis_client.register(VisAppLink)
vis_client.register(VisApiResponse)
vis_client.register(VisThinking)


def vis_name_change(vis_message: str) -> str:
    """Change vis tag name use new name."""
    replacements = {
        "```vis-chart": "```vis-db-chart",
    }

    for old_tag, new_tag in replacements.items():
        vis_message = vis_message.replace(old_tag, new_tag)

    return vis_message
