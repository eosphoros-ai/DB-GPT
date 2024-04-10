"""Blank Action for the Agent."""

import logging
from typing import Optional

from ..resource.resource_api import AgentResource
from .action import Action, ActionOutput

logger = logging.getLogger(__name__)


class BlankAction(Action):
    """Blank action class."""

    def __init__(self):
        """Create a blank action."""
        super().__init__()

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        return None

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action.

        Just return the AI message.
        """
        return ActionOutput(is_exe_success=True, content=ai_message, view=ai_message)
