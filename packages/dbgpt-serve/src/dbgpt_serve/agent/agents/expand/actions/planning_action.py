"""Plan Action."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Type, Union

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.agent.core.action.base import Action, ActionOutput
from dbgpt.agent.core.agent import AgentContext
from dbgpt.agent.core.memory.gpts.base import GptsPlan
from dbgpt.agent.core.memory.gpts.gpts_memory import GptsPlansMemory
from dbgpt.agent.core.schema import Status
from dbgpt.agent.resource.base import AgentResource
from dbgpt.vis.schema import VisPlansContent, VisTaskContent
from dbgpt.vis.vis_converter import SystemVisTag

logger = logging.getLogger(__name__)


class TaskPlan(BaseModel):
    """Plan input model."""

    analysis: Optional[Any] = Field(
        None,
        description="您对上一步执行器代码执行结果的分析，并详细论证‘做了什么’和‘可以得出什么结论’。如果是第一步，请回答‘无’。",
    )
    instruction: str = Field(
        ...,
        description="您下一步的指令。不要涉及复杂的多步骤指令。保持您的指令原子性，明确要求“做什么”和“怎么做”。如果您认为问题已解决，请自行回复摘要。如果您认为问题已解决，请自行回复摘要。如果您认为问题已解决，请自行回复摘要。",
    )
    task_step: str = Field(
        ..., description="当前指令任务的简短总结，简单描述当前所属的步骤或者环节"
    )
    agent: str = Field(..., description="当前任务指令分配给那个代理来完成。")
    task_id: Optional[str] = Field(None, description="任务id")

    def to_dict(self):
        """Convert the object to a dictionary."""
        return model_to_dict(self)


class SrePlanningAction(Action[TaskPlan]):
    """Plan action class."""

    def __init__(self, **kwargs):
        """Create a plan action."""
        super().__init__()
        self.action_view_tag: str = SystemVisTag.VisPlans.value

    @property
    def out_model_type(self):
        """Return the output model type."""
        return TaskPlan

    async def run(
        self,
        ai_message: str = None,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Run the plan action."""
        try:
            context: AgentContext = kwargs["context"]
            message_id = kwargs.get("message_id")
            task_plan: TaskPlan = self._input_convert(ai_message, TaskPlan)

            tasks: List[VisTaskContent] = []

            task_uid = uuid.uuid4().hex
            task_plan.task_id = task_uid
            tasks.append(
                VisTaskContent(
                    task_uid=task_uid,
                    task_id=task_uid,
                    task_title=task_plan.instruction,
                    task_name=task_plan.instruction,
                    task_content=task_plan.analysis,
                    task_parent=None,
                    task_link=None,
                    agent_id=task_plan.agent,
                    agent_name=task_plan.agent,
                    agent_link="",
                    avatar="",
                )
            )
            drsk_plan_content = VisPlansContent(
                uid=uuid.uuid4().hex, type="all", tasks=tasks
            )
            if self.render_protocol:
                view = await self.render_protocol.display(
                    content=drsk_plan_content.to_dict()
                )
            elif need_vis_render:
                raise NotImplementedError("The render_protocol should be implemented.")
            else:
                view = None

            return ActionOutput(
                is_exe_success=True,
                content=json.dumps([task_plan.to_dict()], ensure_ascii=False),
                view=view,
            )
        except Exception as e:
            logger.exception("React Plan Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"React Plan action run failed!{str(e)}"
            )
