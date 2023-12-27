from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from dbgpt.util.json_utils import EnhancedJSONEncoder

from .base import GptsMessage, GptsMessageMemory, GptsPlan, GptsPlansMemory
from .default_gpts_memory import DefaultGptsMessageMemory, DefaultGptsPlansMemory


class GptsMemory:
    def __init__(
        self,
        plans_memory: Optional[GptsPlansMemory] = None,
        message_memory: Optional[GptsMessageMemory] = None,
    ):
        self._plans_memory: GptsPlansMemory = (
            plans_memory if plans_memory is not None else DefaultGptsPlansMemory()
        )
        self._message_memory: GptsMessageMemory = (
            message_memory if message_memory is not None else DefaultGptsMessageMemory()
        )

    @property
    def plans_memory(self):
        return self._plans_memory

    @property
    def message_memory(self):
        return self._message_memory

    async def one_plan_chat_competions(self, conv_id: str):
        plans = self.plans_memory.get_by_conv_id(conv_id=conv_id)
        messages = self.message_memory.get_by_conv_id(conv_id=conv_id)

        messages_group = defaultdict(list)
        for item in messages:
            messages_group[item.current_gogal].append(item)

        plans_info_map = defaultdict()
        for plan in plans:
            plans_info_map[plan.sub_task_content] = {
                "name": plan.sub_task_content,
                "num": plan.sub_task_num,
                "status": plan.state,
                "agent": plan.sub_task_agent,
                "markdown": self._messages_to_agents_vis(
                    messages_group.get(plan.sub_task_content)
                ),
            }

        normal_messages = []
        if messages_group:
            for key, value in messages_group.items():
                if key not in plans_info_map:
                    normal_messages.extend(value)
        return f"{self._messages_to_agents_vis(normal_messages)}\n{self._messages_to_plan_vis(list(plans_info_map.values()))}"

    @staticmethod
    def _messages_to_agents_vis(messages: List[GptsMessage]):
        if messages is None or len(messages) <= 0:
            return ""
        messages_view = []
        for message in messages:
            action_report_str = message.action_report
            view_info = message.content
            if action_report_str and len(action_report_str) > 0:
                action_report = json.loads(action_report_str)
                if action_report:
                    view = action_report.get("view", None)
                    view_info = view if view else action_report.get("content", "")

            messages_view.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "model": message.model_name,
                    "markdown": view_info,
                }
            )
        messages_content = json.dumps(
            messages_view, ensure_ascii=False, cls=EnhancedJSONEncoder
        )
        return f"```agent-messages\n{messages_content}\n```"

    @staticmethod
    def _messages_to_plan_vis(messages: List[Dict]):
        if messages is None or len(messages) <= 0:
            return ""
        messages_content = json.dumps(
            messages, ensure_ascii=False, cls=EnhancedJSONEncoder
        )
        return f"```agent-plans\n{messages_content}\n```"
