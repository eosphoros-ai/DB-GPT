import json
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from dbgpt.agent.actions.action import Action, ActionOutput, T
from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.common.schema import Status
from dbgpt.agent.memory.base import GptsPlan
from dbgpt.agent.memory.gpts_memory import GptsPlansMemory
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.vis.tags.vis_agent_plans import Vis, VisAgentPlans

logger = logging.getLogger(__name__)


class PlanInput(BaseModel):
    serial_number: int = Field(
        0,
        description="子任务的步骤编号",
    )
    agent: str = Field(..., description="用来完成当前步骤的智能代理")
    content: str = Field(..., description="当前步骤的任务内容，确保可以被智能代理执行")
    rely: str = Field(..., description="当前任务执行依赖的其他任务serial_number, 如:1,2,3,  无依赖为空")


class PlanAction(Action[List[PlanInput]]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisAgentPlans()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return None

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return List[PlanInput]

    async def a_run(
        self,
        ai_message: str,
        context: AgentContext,
        plans_memory: GptsPlansMemory,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        try:
            param: List[PlanInput] = self._input_convert(ai_message, List[PlanInput])
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            rensponse_succ = True
            plan_objects = []
            try:
                for item in param:
                    plan = GptsPlan(
                        conv_id=context.conv_id,
                        sub_task_num=item.serial_number,
                        sub_task_content=item.content,
                    )
                    plan.resource_name = ""
                    plan.max_retry_times = context.max_retry_round
                    plan.sub_task_agent = item.agent
                    plan.sub_task_title = item.content
                    plan.rely = item.rely
                    plan.retry_times = 0
                    plan.status = Status.TODO.value
                    plan_objects.append(plan)

                plans_memory.remove_by_conv_id(context.conv_id)
                plans_memory.batch_save(plan_objects)

            except Exception as e:
                logger.exception(str(e))
                fail_reason = f"The generated plan cannot be stored, reason: {str(e)}. Please check whether it is a problem with the plan content. If so, please regenerate the correct plan. If not, please return 'TERMINATE'."
                rensponse_succ = False

            if rensponse_succ:
                plan_content = []
                mk_plans = []
                for item in param:
                    plan_content.append(
                        {
                            "name": item.content,
                            "num": item.serial_number,
                            "status": Status.TODO.value,
                            "agent": item.agent,
                            "rely": item.rely,
                            "markdown": "",
                        }
                    )
                    mk_plans.append(
                        f"- {item.serial_number}.{item.content}[{item.agent}]"
                    )

                # view = await self.render_protocal.disply(content=plan_content)
                view = "\n".join(mk_plans)
                return ActionOutput(
                    is_exe_success=True,
                    content=ai_message,
                    view=view,
                )
            else:
                raise ValueError(fail_reason)
        except Exception as e:
            logger.exception("Plan Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Plan action run failed!{str(e)}"
            )
