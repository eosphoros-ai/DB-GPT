"""GPTs memory."""

import json
from collections import OrderedDict, defaultdict
from typing import Dict, List, Optional

from dbgpt.vis.client import VisAgentMessages, VisAgentPlans, vis_client

from ...action.base import ActionOutput
from .base import GptsMessage, GptsMessageMemory, GptsPlansMemory
from .default_gpts_memory import DefaultGptsMessageMemory, DefaultGptsPlansMemory

NONE_GOAL_PREFIX: str = "none_goal_count_"


class GptsMemory:
    """GPTs memory."""

    def __init__(
        self,
        plans_memory: Optional[GptsPlansMemory] = None,
        message_memory: Optional[GptsMessageMemory] = None,
    ):
        """Create a memory to store plans and messages."""
        self._plans_memory: GptsPlansMemory = (
            plans_memory if plans_memory is not None else DefaultGptsPlansMemory()
        )
        self._message_memory: GptsMessageMemory = (
            message_memory if message_memory is not None else DefaultGptsMessageMemory()
        )

    @property
    def plans_memory(self) -> GptsPlansMemory:
        """Return the plans memory."""
        return self._plans_memory

    @property
    def message_memory(self) -> GptsMessageMemory:
        """Return the message memory."""
        return self._message_memory

    async def _message_group_vis_build(self, message_group):
        if not message_group:
            return ""
        num: int = 0
        last_goal = next(reversed(message_group))
        last_goal_messages = message_group[last_goal]

        last_goal_message = last_goal_messages[-1]
        vis_items = []

        plan_temps = []
        for key, value in message_group.items():
            num = num + 1
            if key.startswith(NONE_GOAL_PREFIX):
                vis_items.append(await self._messages_to_plan_vis(plan_temps))
                plan_temps = []
                num = 0
                vis_items.append(await self._messages_to_agents_vis(value))
            else:
                num += 1
                plan_temps.append(
                    {
                        "name": key,
                        "num": num,
                        "status": "complete",
                        "agent": value[0].receiver if value else "",
                        "markdown": await self._messages_to_agents_vis(value),
                    }
                )

        if len(plan_temps) > 0:
            vis_items.append(await self._messages_to_plan_vis(plan_temps))
        vis_items.append(await self._messages_to_agents_vis([last_goal_message]))
        return "\n".join(vis_items)

    async def _plan_vis_build(self, plan_group: dict[str, list]):
        num: int = 0
        plan_items = []
        for key, value in plan_group.items():
            num = num + 1
            plan_items.append(
                {
                    "name": key,
                    "num": num,
                    "status": "complete",
                    "agent": value[0].receiver if value else "",
                    "markdown": await self._messages_to_agents_vis(value),
                }
            )
        return await self._messages_to_plan_vis(plan_items)

    async def one_chat_completions_v2(self, conv_id: str):
        """Generate a visualization of the conversation."""
        messages = self.message_memory.get_by_conv_id(conv_id=conv_id)
        temp_group: Dict[str, List[GptsMessage]] = OrderedDict()
        none_goal_count = 1
        count: int = 0
        for message in messages:
            count = count + 1
            if count == 1:
                continue
            current_goal = message.current_goal

            last_goal = next(reversed(temp_group)) if temp_group else None
            if last_goal:
                last_goal_messages = temp_group[last_goal]
                if current_goal:
                    if current_goal == last_goal:
                        last_goal_messages.append(message)
                    else:
                        temp_group[current_goal] = [message]
                else:
                    temp_group[f"{NONE_GOAL_PREFIX}{none_goal_count}"] = [message]
                    none_goal_count += 1
            else:
                if current_goal:
                    temp_group[current_goal] = [message]
                else:
                    temp_group[f"{NONE_GOAL_PREFIX}{none_goal_count}"] = [message]
                    none_goal_count += 1

        return await self._message_group_vis_build(temp_group)

    async def one_chat_completions(self, conv_id: str):
        """Generate a visualization of the conversation."""
        messages = self.message_memory.get_by_conv_id(conv_id=conv_id)
        temp_group: Dict[str, List[GptsMessage]] = defaultdict(list)
        temp_messages = []
        vis_items = []
        count: int = 0
        for message in messages:
            count = count + 1
            if count == 1:
                continue
            if not message.current_goal or len(message.current_goal) <= 0:
                if len(temp_group) > 0:
                    vis_items.append(await self._plan_vis_build(temp_group))
                    temp_group.clear()

                temp_messages.append(message)
            else:
                if len(temp_messages) > 0:
                    vis_items.append(await self._messages_to_agents_vis(temp_messages))
                    temp_messages.clear()

                last_goal = message.current_goal
                temp_group[last_goal].append(message)

        if len(temp_group) > 0:
            vis_items.append(await self._plan_vis_build(temp_group))
            temp_group.clear()
        if len(temp_messages) > 0:
            vis_items.append(await self._messages_to_agents_vis(temp_messages, True))
            temp_messages.clear()

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
                if action_out is not None and (
                    action_out.is_exe_success or is_last_message
                ):
                    view = action_out.view
                    view_info = view if view else action_out.content

            messages_view.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "model": message.model_name,
                    "markdown": view_info,
                }
            )
        vis_compent = vis_client.get(VisAgentMessages.vis_tag())
        return await vis_compent.display(content=messages_view)

    async def _messages_to_plan_vis(self, messages: List[Dict]):
        if messages is None or len(messages) <= 0:
            return ""
        return await vis_client.get(VisAgentPlans.vis_tag()).display(content=messages)
