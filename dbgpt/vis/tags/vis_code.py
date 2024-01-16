from typing import Optional

from ..base import Vis


class VisCode(Vis):
    @classmethod
    def vis_tag(cls):
        return "vis-code"
