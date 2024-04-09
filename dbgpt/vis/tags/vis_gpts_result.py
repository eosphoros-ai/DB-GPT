"""Visualize the result of the DBGPts flow."""

from ..base import Vis


class VisDbgptsFlowResult(Vis):
    """Protocol for visualizing the result of the DBGPts flow."""

    @classmethod
    def vis_tag(cls) -> str:
        """Return the tag name of the vis protocol module."""
        return "dbgpts-result"
