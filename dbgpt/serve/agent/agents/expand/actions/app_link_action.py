import json
import logging
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.vis.tags.vis_app_link import Vis, VisAppLink

logger = logging.getLogger(__name__)


class LinkAppInput(BaseModel):
    app_code: Optional[str] = Field(
        ...,
        description="The code of selected app.",
    )
    app_name: Optional[str] = Field(
        ...,
        description="The name of selected app.",
    )


class LinkAppAction(Action[LinkAppInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisAppLink()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return ResourceType.Knowledge

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return LinkAppInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        try:
            param: LinkAppInput = self._input_convert(ai_message, LinkAppInput)
        except Exception as e:
            logger.warning(str(e))
            return ActionOutput(
                is_exe_success=False,
                content=ai_message,
                have_retry=False,
            )
        if not param.app_code or len(param.app_code) <= 0:
            app_link_param = {
                "app_code": "Personal assistant",
                "app_name": "Personal assistant",
                "app_desc": "",
                "app_logo": "",
                "status": "TODO",
            }

            from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent

            return ActionOutput(
                is_exe_success=True,
                content=json.dumps(app_link_param, ensure_ascii=False),
                view=await self.render_protocal.display(content=app_link_param),
                next_speakers=[SummaryAssistantAgent().role],
            )
        else:
            app_link_param = {
                "app_code": param.app_code,
                "app_name": param.app_name,
                "app_desc": "",
                "app_logo": "",
                "status": "TODO",
            }

            from dbgpt.serve.agent.agents.expand.app_start_assisant_agent import (
                StartAppAssistantAgent,
            )

            return ActionOutput(
                is_exe_success=True,
                content=json.dumps(model_to_dict(param), ensure_ascii=False),
                view=await self.render_protocal.display(content=app_link_param),
                next_speakers=[StartAppAssistantAgent().role],
            )
