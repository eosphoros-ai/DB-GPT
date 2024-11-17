"""GPTs memory."""

import asyncio
import json
import logging
from asyncio import Queue
from collections import defaultdict
from typing import Dict, List, Optional, Union

from dbgpt.vis.client import VisAgentMessages, VisAgentPlans, VisAppLink, vis_client

from ...action.base import ActionOutput
from ...schema import Status
from .base import GptsMessage, GptsMessageMemory, GptsPlansMemory
from .default_gpts_memory import DefaultGptsMessageMemory, DefaultGptsPlansMemory

NONE_GOAL_PREFIX: str = "none_goal_count_"

logger = logging.getLogger(__name__)


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

        self.messages_cache: defaultdict = defaultdict(list)
        self.channels: defaultdict = defaultdict(Queue)
        self.enable_vis_map: defaultdict = defaultdict(bool)
        self.start_round_map: defaultdict = defaultdict(int)

    @property
    def plans_memory(self) -> GptsPlansMemory:
        """Return the plans memory."""
        return self._plans_memory

    @property
    def message_memory(self) -> GptsMessageMemory:
        """Return the message memory."""
        return self._message_memory

    def init(
        self,
        conv_id: str,
        enable_vis_message: bool = True,
        history_messages: Optional[List[GptsMessage]] = None,
        start_round: int = 0,
    ):
        """Gpt memory init."""
        self.channels[conv_id] = asyncio.Queue()
        self.enable_vis_map[conv_id] = enable_vis_message
        self.messages_cache[conv_id] = history_messages if history_messages else []
        self.start_round_map[conv_id] = start_round

    def enable_vis_message(self, conv_id):
        """Enable conversation message vis tag."""
        return self.enable_vis_map[conv_id] if conv_id in self.enable_vis_map else True

    def queue(self, conv_id: str):
        """Get conversation message queue."""
        return self.channels[conv_id] if conv_id in self.channels else None

    def clear(self, conv_id: str):
        """Clear gpt memory."""
        # clear last message queue
        queue = self.channels.pop(conv_id)  # noqa
        del queue
        # clear messages cache'
        if self.messages_cache.get(conv_id):
            cache = self.messages_cache.pop(conv_id)  # noqa
            del cache

        # clear vis_enable_tag
        vis_enable_tag = self.enable_vis_map.pop(conv_id)  # noqa
        del vis_enable_tag

        # clear start_roun
        start_round = self.start_round_map.pop(conv_id)  # noqa
        del start_round

    async def push_message(self, conv_id: str, temp_msg: Optional[str] = None):
        """Push conversation message."""
        queue = self.queue(conv_id)
        enable_vis_tag = self.enable_vis_message(conv_id=conv_id)
        if enable_vis_tag:
            # 如果有临时消息内容需要push 拼接再最末尾，否则直接从短期记忆中发布最后消息
            message_view = await self.app_link_chat_message(conv_id)
            if temp_msg:
                temp_view = await self.agent_stream_message(temp_msg)
                message_view = message_view + "\n" + temp_view
            await queue.put(message_view)

        else:
            # 非VIS消息模式，直接推送简单消息列表即可，不做任何处理
            message_views = await self.simple_message(conv_id)
            if temp_msg:
                temp_view = await self.agent_stream_message(temp_msg, False)
                if temp_view and len(temp_view) > 0:
                    message_views.extend(temp_view)
            await queue.put(message_views)

    async def complete(self, conv_id: str):
        """Complete conversation message."""
        queue = self.queue(conv_id)

        await queue.put("[DONE]")

    async def append_message(self, conv_id: str, message: GptsMessage):
        """Append message."""
        # 中期记忆
        self.messages_cache[conv_id].append(message)
        # 长期记忆
        self.message_memory.append(message)

        # 消息记忆后发布消息
        await self.push_message(conv_id)

    async def get_messages(self, conv_id: str) -> List[GptsMessage]:
        """Get conversation message."""
        return self.messages_cache[conv_id]

    async def get_agent_messages(
        self, conv_id: str, agent_role: str
    ) -> List[GptsMessage]:
        """Get agent messages."""
        gpt_messages = self.messages_cache[conv_id]
        result = []
        for gpt_message in gpt_messages:
            if gpt_message.sender == agent_role or gpt_messages.receiver == agent_role:
                result.append(gpt_message)
        return result

    async def get_agent_history_memory(self, conv_id: str, agent_role: str) -> List:
        """Get agent history memory."""
        gpt_messages = self.messages_cache[conv_id]

        agent_messages = []
        for gpt_message in gpt_messages:
            if gpt_message.sender == agent_role or gpt_message.receiver == agent_role:
                agent_messages.append(gpt_message)

        new_list = [
            {
                "question": agent_messages[i].content,
                "ai_message": agent_messages[i + 1].content,
                "action_output": ActionOutput.from_dict(
                    json.loads(agent_messages[i + 1].action_report)
                ),
                "check_pass": agent_messages[i + 1].is_success,
            }
            for i in range(0, len(agent_messages), 2)
        ]

        return new_list

    async def _message_group_vis_build(self, message_group, vis_items: list):
        num: int = 0
        if message_group:
            last_goal = next(reversed(message_group))
            last_goal_message = None
            if not last_goal.startswith(NONE_GOAL_PREFIX):
                last_goal_messages = message_group[last_goal]
                last_goal_message = last_goal_messages[-1]

            plan_temps: List[dict] = []
            need_show_singe_last_message = False
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
                    need_show_singe_last_message = True

            if len(plan_temps) > 0:
                vis_items.append(await self._messages_to_plan_vis(plan_temps))
            if need_show_singe_last_message and last_goal_message:
                vis_items.append(
                    await self._messages_to_agents_vis([last_goal_message], True)
                )
        return "\n".join(vis_items)

    async def agent_stream_message(
        self,
        message: Union[Dict, str],
        enable_vis_message: bool = True,
    ):
        """Get agent stream message."""
        messages_view = []
        if isinstance(message, dict):
            messages_view.append(
                {
                    "sender": message["sender"],
                    "receiver": message["receiver"],
                    "model": message["model"],
                    "markdown": message["markdown"],
                }
            )
        else:
            messages_view.append(
                {
                    "sender": "?",
                    "receiver": "?",
                    "model": "?",
                    "markdown": message,
                }
            )
        if enable_vis_message:
            return await vis_client.get(VisAgentMessages.vis_tag()).display(
                content=messages_view
            )
        else:
            return messages_view

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

    async def simple_message(self, conv_id: str):
        """Get agent simple message."""
        messages_cache = self.messages_cache[conv_id]
        if messages_cache and len(messages_cache) > 0:
            messages = messages_cache
        else:
            messages = self.message_memory.get_by_conv_id(conv_id=conv_id)

        simple_message_list = []
        for message in messages:
            if message.sender == "Human":
                continue

            action_report_str = message.action_report
            view_info = message.content
            action_out = None
            if action_report_str and len(action_report_str) > 0:
                action_out = ActionOutput.from_dict(json.loads(action_report_str))
            if action_out is not None:
                view_info = action_out.content

            simple_message_list.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "model": message.model_name,
                    "markdown": view_info,
                }
            )

        return simple_message_list

    async def app_link_chat_message(self, conv_id: str):
        """Get app link chat message."""
        messages = []
        if conv_id in self.messages_cache:
            messages_cache = self.messages_cache[conv_id]
            if messages_cache and len(messages_cache) > 0:
                start_round = (
                    self.start_round_map[conv_id]
                    if conv_id in self.start_round_map
                    else 0
                )
                messages = messages_cache[start_round:]
        else:
            messages = self.message_memory.get_by_conv_id(conv_id=conv_id)

        # VIS消息组装
        temp_group: Dict = {}
        app_link_message: Optional[GptsMessage] = None
        app_lanucher_message: Optional[GptsMessage] = None

        none_goal_count = 1
        for message in messages:
            if message.sender in [
                "Intent Recognition Expert",
                "App Link",
            ] or message.receiver in ["Intent Recognition Expert", "App Link"]:
                if (
                    message.sender in ["Intent Recognition Expert", "App Link"]
                    and message.receiver == "AppLauncher"
                ):
                    app_link_message = message
                if message.receiver != "Human":
                    continue

            if message.sender == "AppLauncher":
                if message.receiver == "Human":
                    app_lanucher_message = message
                continue

            current_gogal = message.current_goal

            last_goal = next(reversed(temp_group)) if temp_group else None
            if last_goal:
                last_goal_messages = temp_group[last_goal]
                if current_gogal:
                    if current_gogal == last_goal:
                        last_goal_messages.append(message)
                    else:
                        temp_group[current_gogal] = [message]
                else:
                    temp_group[f"{NONE_GOAL_PREFIX}{none_goal_count}"] = [message]
                    none_goal_count += 1
            else:
                if current_gogal:
                    temp_group[current_gogal] = [message]
                else:
                    temp_group[f"{NONE_GOAL_PREFIX}{none_goal_count}"] = [message]
                    none_goal_count += 1

        vis_items: list = []
        if app_link_message:
            vis_items.append(
                await self._messages_to_app_link_vis(
                    app_link_message, app_lanucher_message
                )
            )

        return await self._message_group_vis_build(temp_group, vis_items)

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

            messages_view.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "model": message.model_name,
                    "markdown": view_info,
                    "resource": (
                        message.resource_info if message.resource_info else None
                    ),
                }
            )
        return await vis_client.get(VisAgentMessages.vis_tag()).display(
            content=messages_view
        )

    async def _messages_to_plan_vis(self, messages: List[Dict]):
        if messages is None or len(messages) <= 0:
            return ""
        return await vis_client.get(VisAgentPlans.vis_tag()).display(content=messages)

    async def _messages_to_app_link_vis(
        self, link_message: GptsMessage, lanucher_message: Optional[GptsMessage] = None
    ):
        logger.info("app link vis build")
        if link_message is None:
            return ""
        param = {}
        link_report_str = link_message.action_report
        if link_report_str and len(link_report_str) > 0:
            action_out = ActionOutput.from_dict(json.loads(link_report_str))
            if action_out is not None:
                if action_out.is_exe_success:
                    temp = json.loads(action_out.content)

                    param["app_code"] = temp["app_code"]
                    param["app_name"] = temp["app_name"]
                    param["app_desc"] = temp.get("app_desc", "")
                    param["app_logo"] = ""
                    param["status"] = Status.RUNNING.value

                else:
                    param["status"] = Status.FAILED.value
                    param["msg"] = action_out.content

        if lanucher_message:
            lanucher_report_str = lanucher_message.action_report
            if lanucher_report_str and len(lanucher_report_str) > 0:
                lanucher_action_out = ActionOutput.from_dict(
                    json.loads(lanucher_report_str)
                )
                if lanucher_action_out is not None:
                    if lanucher_action_out.is_exe_success:
                        param["status"] = Status.COMPLETE.value
                    else:
                        param["status"] = Status.FAILED.value
                        param["msg"] = lanucher_action_out.content
        else:
            param["status"] = Status.COMPLETE.value
        return await vis_client.get(VisAppLink.vis_tag()).display(content=param)

    async def chat_messages(
        self,
        conv_id: str,
    ):
        """Get chat messages."""
        while True:
            queue = self.queue(conv_id)
            if not queue:
                break
            item = await queue.get()
            if item == "[DONE]":
                queue.task_done()
                break
            else:
                yield item
                await asyncio.sleep(0.005)
