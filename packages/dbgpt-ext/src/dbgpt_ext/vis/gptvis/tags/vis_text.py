from dbgpt.vis.base import Vis


class VisText(Vis):
    """VisThinking."""

    def sync_display(self, **kwargs) -> str:
        """Display the content using the vis protocol."""
        content = kwargs.get("content")

        try:
            return content.get("markdown", "")
        except Exception:
            return str(content)

    @classmethod
    def vis_tag(cls):
        """Vis tag name.

        Returns:
            str: The tag name associated with the visualization.
        """
        return "vis-text"
