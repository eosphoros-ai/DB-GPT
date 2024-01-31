import json
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from dbgpt.agent.actions.action import Action, ActionOutput, T
from dbgpt.agent.common.schema import Status
from dbgpt.agent.plugin.generator import PluginPromptGenerator
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.agent.resource.resource_plugin_api import ResourcePluginClient
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

logger = logging.getLogger(__name__)


class BlankAction(Action):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return None

    @property
    def render_protocal(self) -> Optional[Vis]:
        return None

    @property
    def ai_out_schema(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        return None

    async def a_run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        return ActionOutput(is_exe_success=True, content=ai_message, view=ai_message)
