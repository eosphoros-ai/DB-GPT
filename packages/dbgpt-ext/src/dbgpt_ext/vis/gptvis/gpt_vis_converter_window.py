import json
import logging
from typing import Dict, List, Optional, Union

from dbgpt.agent import ActionOutput
from dbgpt.agent.core.memory.gpts import GptsMessage, GptsPlan
from dbgpt.vis.vis_converter import SystemVisTag
from dbgpt_ext.vis.gptvis.gpt_vis_converter import GptVisConverter, GptVisTagPackage

NONE_GOAL_PREFIX: str = "none_goal_count_"
logger = logging.getLogger(__name__)


class GptVisLRConverter(GptVisConverter):
    def __init__(self, paths: Optional[str] = None):
        default_tag_paths = ["dbgpt_ext.vis.gptvis.tags"]
        super().__init__(paths if paths else default_tag_paths)

    async def visualization(
        self,
        messages: List[GptsMessage],
        plans_map: Optional[Dict[str, GptsPlan]] = None,
        gpt_msg: Optional[GptsMessage] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
        is_first_chunk: bool = False,
        incremental: bool = False,
    ):
        ### left区域
        left = await self._message_tasks_vis_build(messages, plans_map)
        ### rigth区域
        right = await self._message_tabs_vis_build(messages, plans_map)

        return json.dumps({"left": left, "right": right})

    async def _message_tasks_vis_build(
        self,
        messages: List,
        plans_map: Optional[Dict[str, GptsPlan]] = None,
    ):
        num: int = 0
        vis_items: list = []
        task_group: Dict = {}
        for message in messages:
            current_gogal = message.current_goal
            if current_gogal in task_group:
                task_group[current_gogal].append(message)
            else:
                task_group[current_gogal] = [message]

        plan_temps: List[dict] = []
        for key, value in task_group.items():
            num += 1
            plan: GptsPlan = plans_map.get(value[-1].current_goal)
            if plan:
                plan_temps.append(
                    {
                        "name": plan.sub_task_title,
                        "content": plan.sub_task_content,
                        "num": num,
                        "avatar": value[-1].avatar,
                        "status": plan.state,
                        "task_id": plan.sub_task_id,
                        "model": plan.agent_model,
                        "agent": plan.sub_task_agent,
                        "tasks": [],
                    }
                )
            else:
                plan_temps.append(
                    {
                        "task_id": value[0].message_id,
                        "name": key,
                        "avatar": value[-1].avatar,
                        "content": key,
                        "num": num,
                        "status": "complete",
                        "agent": value[-1].sender_name if value else "",
                        "tasks": [],
                    }
                )
        if len(plan_temps) > 0:
            tasks_vis = self.vis_inst(GptVisTagPackage.VisTasks.value).sync_display(
                content=plan_temps
            )
            vis_items.append(tasks_vis)
        return "\n".join(vis_items)

    async def _message_tabs_vis_build(
        self,
        messages,
        plans_map: Optional[Dict[str, GptsPlan]] = None,
    ):
        num: int = 0
        vis_items: list = []
        task_group: Dict = {}
        for message in messages:
            current_gogal = message.current_goal
            if current_gogal in task_group:
                task_group[current_gogal].append(message)
            else:
                task_group[current_gogal] = [message]

        plan_temps: List[dict] = []
        for key, value in task_group.items():
            num += 1
            plan: GptsPlan = plans_map.get(value[-1].current_goal)
            if plan:
                plan_temps.append(
                    {
                        "name": plan.sub_task_title,
                        "num": num,
                        "task_id": plan.sub_task_id,
                        "status": plan.state,
                        "avatar": value[-1].avatar,
                        "model": plan.agent_model,
                        "agent": plan.sub_task_agent,
                        "markdown": await self._messages_to_agents_vis(value),
                    }
                )
            else:
                plan_temps.append(
                    {
                        "task_id": value[0].message_id,
                        "name": key,
                        "num": num,
                        "avatar": value[-1].avatar,
                        "status": "complete",
                        "agent": value[0].sender_name if value else "",
                        "markdown": await self._messages_to_agents_vis(value),
                    }
                )
        if len(plan_temps) > 0:
            tasks_vis = self.vis_inst(GptVisTagPackage.VisTabs.value).sync_display(
                content=plan_temps
            )
            vis_items.append(tasks_vis)
        return "\n".join(vis_items)

    async def _messages_to_agents_vis(
        self, messages: List[GptsMessage], is_last_message: bool = False
    ):
        if messages is None or len(messages) <= 0:
            return ""
        messages_view = []
        for message in messages:
            action_report_str = message.action_report
            view_info = message.content
            if action_report_str and len(action_report_str) > 0:
                action_out = ActionOutput.from_dict(json.loads(action_report_str))
                if action_out is not None:  # noqa
                    if action_out.is_exe_success or is_last_message:  # noqa
                        view = action_out.view
                        view_info = view if view else action_out.content

            thinking = message.thinking
            vis_thinking = self.vis_inst(SystemVisTag.VisThinking.value)
            if thinking:
                vis_thinking = vis_thinking.sync_display(content=thinking)
                view_info = vis_thinking + "\n" + view_info

            messages_view.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "avatar": message.avatar,
                    "model": message.model_name,
                    "markdown": view_info,
                    "resource": (
                        message.resource_info if message.resource_info else None
                    ),
                }
            )
        return await self.vis_inst(GptVisTagPackage.AgentMessage.value).display(
            content=messages_view
        )
