"""Visualize plugins."""
from ..base import Vis


class VisPlugin(Vis):
    """Protocol for visualizing plugins."""

    @classmethod
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol module."""
        return "vis-plugin"
