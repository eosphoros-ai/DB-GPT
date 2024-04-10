"""Code visualization protocol."""
from ..base import Vis


class VisCode(Vis):
    """Protocol for visualizing code."""

    @classmethod
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol module."""
        return "vis-code"
