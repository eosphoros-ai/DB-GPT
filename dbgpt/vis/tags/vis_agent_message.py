from typing import Optional

from ..base import Vis


class VisAgentMessages(Vis):
    @classmethod
    def vis_tag(cls):
        return "agent-messages"
