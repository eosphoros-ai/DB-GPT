"""Plan Action."""

import logging
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_agent_plans import Vis, VisAgentPlans

from ...resource.base import AgentResource
from ..action.base import Action, ActionOutput
from ..agent import AgentContext
from ..memory.gpts.base import GptsPlan
from ..memory.gpts.gpts_memory import GptsPlansMemory
from ..schema import Status

logger = logging.getLogger(__name__)


class PlanInput(BaseModel):
    """Plan input model."""

    serial_number: int = Field(
        0,
        description="Number of sub-tasks",
    )
    agent: str = Field(..., description="The agent name to complete current task")
    content: str = Field(
        ...,
        description="The task content of current step, make sure it can by executed by"
        " agent",
    )
    rely: str = Field(
        ...,
        description="The rely task number(serial_number), e.g. 1,2,3, empty if no rely",
    )


class PlanAction(Action[List[PlanInput]]):
    """Plan action class."""

    def __init__(self, **kwargs):
        """Create a plan action."""
        super().__init__(**kwargs)
        self._render_protocol = VisAgentPlans()

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Output model type."""
        return List[PlanInput]

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Run the plan action."""
        context: AgentContext = kwargs["context"]
        plans_memory: GptsPlansMemory = kwargs["plans_memory"]
        try:
            param: List[PlanInput] = self._input_convert(ai_message, List[PlanInput])
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        fail_reason = ""

        try:
            response_success = True
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
                    plan.state = Status.TODO.value
                    plan_objects.append(plan)

                plans_memory.remove_by_conv_id(context.conv_id)
                plans_memory.batch_save(plan_objects)

            except Exception as e:
                logger.exception(str(e))
                fail_reason = (
                    f"The generated plan cannot be stored, reason: {str(e)}."
                    f" Please check whether it is a problem with the plan content. "
                    f"If so, please regenerate the correct plan. If not, please return"
                    f" 'TERMINATE'."
                )
                response_success = False

            if response_success:
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
