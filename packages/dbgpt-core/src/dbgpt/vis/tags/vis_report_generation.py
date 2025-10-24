"""Vis Report Generation."""

from typing import Any, Dict, Optional

from ..base import Vis


class VisReportGeneration(Vis):
    """VisReportGeneration."""

    @classmethod
    def vis_tag(cls):
        """Vis tag name.

        Returns:
            str: The tag name associated with the visualization.
        """
        return "report-generation"

    async def display(self, content: Dict[str, Any]) -> Optional[str]:
        """Display the visualization content."""
        if not content:
            return None

        report_content = content
        return report_content
