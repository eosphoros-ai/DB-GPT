import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.agent import Action, ActionOutput, AgentResource
from dbgpt.serve.agent.agents.expand.actions.intent_recognition_action import (
    IntentRecognitionInput,
)
from dbgpt.serve.agent.db.gpts_app import GptsApp, GptsAppDao
from dbgpt.serve.agent.team.base import TeamMode
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

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
    app_desc: Optional[str] = Field(
        ...,
        description="The new user input.",
    )


class StartAppAction(Action[LinkAppInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisPlugin()

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return IntentRecognitionInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        conv_id = kwargs.get("conv_id")
        user_input = kwargs.get("user_input")
        paren_agent = kwargs.get("paren_agent")
        init_message_rounds = kwargs.get("init_message_rounds")

        try:
            param: LinkAppInput = self._input_convert(ai_message, LinkAppInput)
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        new_user_input = param.app_desc
        try:
            gpts_dao = GptsAppDao()
            gpts_app: GptsApp = gpts_dao.app_detail(param.app_code)
            if not gpts_app:
                return ActionOutput(
                    is_exe_success=False,
                    content=ai_message,
                    view=f"[DBGPT Warning] Intent definition application cannot be found [{param.app_code}]{param.app_name}",
                    have_retry=False,
                )
            if TeamMode.NATIVE_APP.value == gpts_app.team_mode:
                return ActionOutput(
                    is_exe_success=False,
                    content=ai_message,
                    view="[DBGPT Warning] Native application connection startup is not supported for the time being.",
                    have_retry=False,
                )
            else:
                from dbgpt.serve.agent.agents.controller import multi_agents

                await multi_agents.agent_team_chat_new(
                    new_user_input if new_user_input else user_input,
                    conv_id,
                    gpts_app,
                    paren_agent.memory,
                    False,
                    link_sender=paren_agent,
                    app_link_start=True,
                    init_message_rounds=init_message_rounds,
                )

                return ActionOutput(
                    is_exe_success=True, content="", view=None, have_retry=False
                )
        except Exception as e:
            logger.exception(f"App [{param.app_code}] excute Failed!")
            return ActionOutput(
                is_exe_success=False,
                content=ai_message,
                view=f"[DBGPT Warning] An exception occurred during the answering process of linked application [{param.app_code}]{param.intent},{str(e)}",
                have_retry=False,
            )
