from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from .tags.vis_code import VisCode
from .tags.vis_chart import VisChart
from .tags.vis_dashboard import VisDashboard
from .tags.vis_agent_plans import VisAgentPlans
from .tags.vis_agent_message import VisAgentMessages
from .tags.vis_plugin import VisPlugin
from .base import Vis


class VisClient:
    def __init__(self):
        self._vis_tag: Dict[str, Vis] = {}

    def register(self, vis_cls: Vis):
        self._vis_tag[vis_cls.vis_tag()] = vis_cls()

    def get(self, tag_name):
        if tag_name not in self._vis_tag:
            raise ValueError(f"Vis protocol tags not yet supported！[{tag_name}]")
        return self._vis_tag[tag_name]

    def tag_names(self):
        self._vis_tag.keys()


vis_client = VisClient()

vis_client.register(VisCode)
vis_client.register(VisChart)
vis_client.register(VisDashboard)
vis_client.register(VisAgentPlans)
vis_client.register(VisAgentMessages)
vis_client.register(VisPlugin)
