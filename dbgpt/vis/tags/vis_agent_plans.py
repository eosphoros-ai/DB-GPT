from typing import Optional

from ..base import Vis


class VisAgentPlans(Vis):
    @classmethod
    def vis_tag(cls):
        return "agent-plans"
