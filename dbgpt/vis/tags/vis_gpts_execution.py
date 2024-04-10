"""Agent Plans Vis Protocol."""

from ..base import Vis


class VisDbgptsFlow(Vis):
    """DBGPts Flow Vis Protocol."""

    @classmethod
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol module."""
        return "dbgpts-flow"
