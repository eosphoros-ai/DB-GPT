from typing import Optional

from ..base import Vis


class VisPlugin(Vis):
    @classmethod
    def vis_tag(cls):
        return "vis-plugin"
