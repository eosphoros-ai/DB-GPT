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


class TaskParam(BaseModel):
    """Plan input model."""

    task_id: Any = Field(
        ...,
        description="任务编号",
    )
    parent_id: Any = Field(
        ...,
        description="父任务编号",
    )
    task_goal: str = Field(
        ...,
        description="任务目标内容",
    )
    agent: str = Field(..., description="当前任务可交给那个代理完成")
    assertion: str = Field(
        None,
        description="当目标的判断规则和标准",
    )
    slots: dict = Field(
        None,
        description="提取到的用户输入的参数信息",
    )

    def to_dict(self):
        """Convert the object to a dictionary."""
        return model_to_dict(self)


class ReActAction(Action[List[TaskParam]]):
    """Plan action class."""

    def __init__(self, **kwargs):
        """Create a plan action."""
        super().__init__()
        self.action_view_tag: str = SystemVisTag.VisPlans.value

    @property
    def out_model_type(self):
        """Return the output model type."""
        return List[TaskParam]

    def _create_example(
        self,
        model_type: Union[Type[BaseModel], List[Type[BaseModel]]],
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        return [
            {
                "parent_id": "父任务编号，当前任务是根据之前的那个任务逻辑推导得出，标记任务逻辑血缘，默认0作为所有无血缘任务的父任务",
                "task_id": "当前任务编号,如果存在父任务，确保当前任务编号大于父任务的最大子任务序号，同一个父任务下，任务序号不能重复 ",
                "task_goal": "任务目标x",
                "agent": "当前任务可交给那个代理完成",
                "assertion": "当目标的判断规则和标准",
                "slots": {
                    "参数名1": "当前任务关联的具体目标等参数值信息1",
                    "参数名2": "当前任务关联的具体目标等参数值信息2",
                },
            }
        ]

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Run the plan action."""
        try:
            context: AgentContext = kwargs["context"]
            plans_memory: GptsPlansMemory = kwargs["plans_memory"]
            message_id = kwargs.get("message_id")
            task_params: List[TaskParam] = self._input_convert(
                ai_message, List[TaskParam]
            )

            plan_objects = []

            tasks: List[VisTaskContent] = []

            for item in task_params:
                task_uid = uuid.uuid4().hex
                plan = GptsPlan(
                    conv_id=context.conv_id,
                    task_uid=task_uid,
                    sub_task_num=0,
                    sub_task_id=item.task_id,
                    sub_task_title=item.task_goal,
                    sub_task_content=json.dumps(item.slots),
                    task_parent=item.parent_id,
                    conv_round=kwargs.get("round", 0),
                    conv_round_id=kwargs.get("round_id", None),
                    resource_name=None,
                    max_retry_times=context.max_retry_round,
                    sub_task_agent=item.agent,
                    retry_times=kwargs.get("retry_times", 0),
                    state=Status.TODO.value,
                )

                plan_objects.append(plan)

                tasks.append(
                    VisTaskContent(
                        task_uid=task_uid,
                        task_id=str(item.task_id),
                        task_title=item.task_goal,
                        task_name=item.task_goal,
                        task_content=json.dumps(item.slots),
                        task_parent=str(item.parent_id),
                        task_link=None,
                        agent_id=item.agent,
                        agent_name=item.agent,
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

            ## 任务规划记录，方便后续做进展跟踪
            # plans_memory.remove_by_conv_id(context.conv_id)
            plans_memory.batch_save(plan_objects)

            return ActionOutput(
                is_exe_success=True,
                content=json.dumps(
                    [item.to_dict() for item in task_params], ensure_ascii=False
                ),
                view=view,
            )
        except Exception as e:
            logger.exception("React Plan Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"React Plan action run failed!{str(e)}"
            )
