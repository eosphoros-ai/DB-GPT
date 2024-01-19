from typing import Optional

from ..base import Vis


class VisDbgptsFlow(Vis):
    @classmethod
    def vis_tag(cls):
        return "dbgpts-flow"
