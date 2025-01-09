"""Base class for vis protocol module."""
import json
from typing import Any, Dict, Optional

from dbgpt.util.json_utils import serialize


class Vis:
    """Vis protocol base class."""

    def render_prompt(self) -> Optional[str]:
        """Return the prompt for the vis protocol."""
        return None

    async def generate_param(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Generate the parameters required by the vis protocol.

        Display corresponding content using vis protocol
        Args:
            **kwargs:

        Returns:
        vis protocol text
        """
        return kwargs["content"]

    async def display(self, **kwargs) -> Optional[str]:
        """Display the content using the vis protocol."""
        content = json.dumps(
            await self.generate_param(**kwargs), default=serialize, ensure_ascii=False
        )
        return f"```{self.vis_tag()}\n{content}\n```"

    @classmethod
    def vis_tag(cls) -> str:
        """Return current vis protocol module tag name."""
        return ""
