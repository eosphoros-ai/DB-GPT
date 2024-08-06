import logging
from typing import Optional

from dbgpt.agent import Action, ActionOutput, AgentResource, ConversableAgent
from dbgpt.serve.agent.agents.expand.actions.app_link_action import LinkAppInput
from dbgpt.serve.agent.db.gpts_app import GptsApp, GptsAppDao
from dbgpt.serve.agent.team.base import TeamMode
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

logger = logging.getLogger(__name__)


class StartAppAction(Action[LinkAppInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisPlugin()

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return LinkAppInput

    async def run(
        self,
        ai_message: str,
        user_input: str,
        conv_id: str,
        paren_agent: ConversableAgent,
        init_message_rounds: int,
        sender: Optional[ConversableAgent] = None,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        try:
            param: LinkAppInput = self._input_convert(ai_message, LinkAppInput)
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            gpts_dao = GptsAppDao()
            gpts_app: GptsApp = gpts_dao.app_detail(param.app_code)
            if not gpts_app:
                return ActionOutput(
                    is_exe_success=False,
                    content=f"链接智能体{param.app_name}信息配置异常无法找到",
                    view=f"链接智能体{param.app_name}信息配置异常无法找到",
                    have_retry=False,
                )
            if TeamMode.NATIVE_APP.value == gpts_app.team_mode:
                return ActionOutput(
                    is_exe_success=False,
                    content="暂时不支持原生应用连接启动",
                    view="暂时不支持原生应用连接启动",
                    have_retry=False,
                )
            else:
                from dbgpt.serve.agent.agents.controller import multi_agents

                # TODO 仅启动应用，不需要返回信息
                await multi_agents.agent_team_chat_new(
                    user_input,
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
                content=f"应用[{param.app_name}]回答失败!{str(e)}",
                view=f"应用[{param.app_name}]回答失败!{str(e)}",
                have_retry=False,
            )
