from ..base import Vis


class VisThinking(Vis):
    """VisThinking."""

    @classmethod
    async def build_message(cls, message: str) -> str:
        vis = VisThinking()
        return f"```{vis.vis_tag()}\n{message}\n```"

    def sync_display(self, **kwargs) -> str:
        """Display the content using the vis protocol."""
        content = kwargs.get("content")
        return f"```{self.vis_tag()}\n{content}\n```"

    @classmethod
    def vis_tag(cls):
        """Vis tag name.

        Returns:
            str: The tag name associated with the visualization.
        """
        return "vis-thinking"
