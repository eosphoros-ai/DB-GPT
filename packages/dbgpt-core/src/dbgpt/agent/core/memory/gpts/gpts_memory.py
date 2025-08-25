"""GPTs memory."""

import asyncio
import json
import logging
from asyncio import Queue
from collections import defaultdict
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Dict, List, Optional, Union

from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.id_generator import IdGenerator
from dbgpt.vis.client import VisAgentMessages, VisAgentPlans, VisAppLink, vis_client
from dbgpt.vis.vis_converter import DefaultVisConverter, VisProtocolConverter

from ...action.base import ActionOutput
from ...schema import Status
from .base import GptsMessage, GptsMessageMemory, GptsPlan, GptsPlansMemory
from .default_gpts_memory import DefaultGptsMessageMemory, DefaultGptsPlansMemory

NONE_GOAL_PREFIX: str = "none_goal_count_"

logger = logging.getLogger(__name__)


class GptsMemory:
    """GPTs memory."""

    def __init__(
        self,
        plans_memory: Optional[GptsPlansMemory] = None,
        message_memory: Optional[GptsMessageMemory] = None,
        executor: Optional[Executor] = None,
    ):
        """Create a memory to store plans and messages."""
        self._plans_memory: GptsPlansMemory = (
            plans_memory if plans_memory is not None else DefaultGptsPlansMemory()
        )
        self._message_memory: GptsMessageMemory = (
            message_memory if message_memory is not None else DefaultGptsMessageMemory()
        )
        self._executor = executor or ThreadPoolExecutor(max_workers=2)

        self.messages_cache_new: defaultdict = defaultdict(dict)
        self.messages_id_cache: defaultdict = defaultdict(list)
        self._message_rounds_generator: dict[str, IdGenerator] = {}
        self.view_cache: defaultdict = defaultdict(list)
        self.plans_cache: defaultdict = defaultdict(list)
        self.channels: defaultdict = defaultdict(Queue)
        self.enable_vis_map: defaultdict = defaultdict(bool)
        self.start_round_map: defaultdict = defaultdict(int)
        self._vis_converter: VisProtocolConverter = DefaultVisConverter()

    @property
    def vis_converter(self):
        """Return the vis converter"""
        return self._vis_converter

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
        vis_converter: Optional[VisProtocolConverter] = None,
        start_round: int = 0,
    ):
        """Gpt memory init."""
        self.channels[conv_id] = asyncio.Queue()
        if history_messages:
            self._cache_messages(conv_id, history_messages)
        self.enable_vis_map[conv_id] = enable_vis_message
        # self.messages_cache[conv_id] = history_messages if history_messages else []
        self.start_round_map[conv_id] = start_round
        self._message_rounds_generator[conv_id] = IdGenerator(start_round + 1)
        if vis_converter:
            self._vis_converter = vis_converter

    def enable_vis_message(self, conv_id):
        """Enable conversation message vis tag."""
        return self.enable_vis_map[conv_id] if conv_id in self.enable_vis_map else True

    def _cache_messages(self, conv_id: str, messages: List[GptsMessage]):
        for message in messages:
            self.messages_cache_new[conv_id][message.message_id] = message
            if message.message_id not in self.messages_id_cache[conv_id]:
                self.messages_id_cache[conv_id].append(message.message_id)

    async def load_persistent_memory(self, conv_id: str):
        """Load persistent memory."""
        if conv_id not in self.messages_id_cache:
            messages = await blocking_func_to_async(
                self._executor, self.message_memory.get_by_conv_id, conv_id
            )
            self._cache_messages(conv_id, messages)

        if conv_id not in self.plans_cache:
            plans = await blocking_func_to_async(
                self._executor, self.plans_memory.get_by_conv_id, conv_id
            )
            self.plans_cache[conv_id] = plans

    def queue(self, conv_id: str):
        """Get conversation message queue."""
        return self.channels[conv_id] if conv_id in self.channels else None

    def clear(self, conv_id: str):
        """Clear gpt memory."""
        # clear last message queue
        queue = self.channels.pop(conv_id)  # noqa
        del queue
        # clear messages cache'
        # if self.messages_cache.get(conv_id):
        #     cache = self.messages_cache.pop(conv_id)  # noqa
        #     del cache

        # clear messages cache_new
        if self.messages_cache_new.get(conv_id):
            cache_new = self.messages_cache_new.pop(conv_id)  # noqa
            del cache_new
        if self.messages_id_cache.get(conv_id):
            id_cache = self.messages_id_cache.pop(conv_id)  # noqa
            del id_cache

        # clear view cache
        if self.view_cache.get(conv_id):
            view_cache = self.view_cache.pop(conv_id)  # noqa
            del view_cache

        # clear start_roun
        start_round = self.start_round_map.pop(conv_id)  # noqa
        del start_round

        # clear message rounds generator
        if self._message_rounds_generator.get(conv_id):
            rounds_generator = self._message_rounds_generator.pop(conv_id)  # noqa
            del rounds_generator

    async def next_message_rounds(self, conv_id: str) -> int:
        return await self._message_rounds_generator[conv_id].next()

    async def push_message(
        self,
        conv_id: str,
        gpt_msg: Optional[GptsMessage] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
        is_first_chunk: bool = False,
        incremental: bool = False,
    ):
        """Push conversation message."""

        from .... import UserProxyAgent

        if gpt_msg and gpt_msg.sender == UserProxyAgent().role:
            return
        final_view = await self.vis_messages(
            conv_id,
            gpt_msg,
            stream_msg,
            is_first_chunk=is_first_chunk,
            incremental=incremental,
        )
        self.view_cache[conv_id] = final_view
        queue = self.queue(conv_id)
        if not queue:
            logger.warning(f"There is no message channel available for it！{conv_id}")
        else:
            await queue.put(final_view)

    async def vis_final(self, conv_id: str):
        messages = await self.get_messages(conv_id)
        start_round = (
            self.start_round_map[conv_id] if conv_id in self.start_round_map else 0
        )
        messages = messages[start_round:]

        ## merge messages
        messages = self._merge_messages(messages)
        plans = await self.get_plans(conv_id=conv_id)

        ## 消息可视化布局转换
        vis_view = await self._vis_converter.final_view(
            messages=messages,
            plans_map={item.sub_task_content: item for item in plans},
        )
        return vis_view

    async def vis_messages(
        self,
        conv_id: str,
        gpt_msg: Optional[GptsMessage] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
        is_first_chunk: bool = False,
        incremental: bool = False,
    ):
        """Get all persistent messages that have been converted through the visualization protocol(excluding the part that is currently being streamed.)"""
        ## 消息数据流准备
        messages = await self.get_messages(conv_id)
        start_round = (
            self.start_round_map[conv_id] if conv_id in self.start_round_map else 0
        )
        messages = messages[start_round:]

        ## merge messages
        messages = self._merge_messages(messages)

        plans = await self.get_plans(conv_id=conv_id)
        ## 消息可视化布局转换
        vis_view = await self._vis_converter.visualization(
            messages=messages,
            plans_map={item.sub_task_content: item for item in plans},
            gpt_msg=gpt_msg,
            stream_msg=stream_msg,
            is_first_chunk=is_first_chunk,
            incremental=incremental,
        )
        return vis_view

    def _merge_messages(self, messages: List[GptsMessage]):
        i = 0
        new_messages: List[GptsMessage] = []

        while i < len(messages):
            cu_item = messages[i]

            # 屏蔽用户消息
            # if cu_item.sender == UserProxyAgent().role:
            if cu_item.sender == "Human":
                i += 1
                continue
            if not cu_item.show_message:
                ## 接到消息的Agent不展示消息，消息直接往后传递展示
                if i + 1 < len(messages):
                    ne_item = messages[i + 1]
                    new_message = ne_item
                    new_message.sender = cu_item.sender
                    new_message.current_goal = (
                        ne_item.current_goal or cu_item.current_goal
                    )
                    new_message.resource_info = (
                        ne_item.resource_info or cu_item.resource_info
                    )
                    new_messages.append(new_message)
                    i += 2  # 两个消息合并为一个
                    continue
            new_messages.append(cu_item)
            i += 1

        return new_messages

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

    async def complete(self, conv_id: str):
        """Complete conversation message."""
        queue = self.queue(conv_id)
        if queue:
            await queue.put("[DONE]")

    async def append_message(
        self,
        conv_id: str,
        message: GptsMessage,
        incremental: bool = False,
        save_db: bool = True,
    ):
        """Append message."""
        # Add and update messages based on message_id
        # Cache messages
        self._cache_messages(conv_id, [message])
        # Message persistence storage
        if save_db:
            await blocking_func_to_async(
                self._executor, self.message_memory.update, message
            )
        # Publish and display message
        await self.push_message(conv_id, message, incremental=incremental)

    async def get_messages(self, conv_id: str) -> List[GptsMessage]:
        """Get message by conv_id."""
        if conv_id not in self.messages_id_cache:
            await self.load_persistent_memory(conv_id)

        messages = []
        for msg_id in self.messages_id_cache[conv_id]:
            messages.append(self.messages_cache_new[conv_id][msg_id])
        ## 根据rounds排序
        messages.sort(key=lambda x: x.rounds)
        return messages

    async def get_agent_messages(
        self, conv_id: str, agent_role: str
    ) -> List[GptsMessage]:
        """Get agent messages."""
        gpt_messages = self.get_messages[conv_id]
        result = []
        for gpt_message in gpt_messages:
            if gpt_message.sender == agent_role or gpt_messages.receiver == agent_role:
                result.append(gpt_message)
        return result

    async def get_agent_history_memory(
        self, conv_id: str, agent_role: str
    ) -> List[ActionOutput]:
        """Get agent history memory."""

        agent_messages = await blocking_func_to_async(
            self._executor, self.message_memory.get_by_agent, conv_id, agent_role
        )
        new_list = []
        for i in range(0, len(agent_messages), 2):
            if i + 1 >= len(agent_messages):
                break
            action_report = None
            if agent_messages[i + 1].action_report:
                action_report = ActionOutput.from_dict(
                    json.loads(agent_messages[i + 1].action_report)
                )
            new_list.append(
                {
                    "question": agent_messages[i].content,
                    "ai_message": agent_messages[i + 1].content,
                    "action_output": action_report,
                    "check_pass": agent_messages[i + 1].is_success,
                }
            )

        # Just use the action_output now
        return [m["action_output"] for m in new_list if m["action_output"]]

    async def append_plans(self, conv_id: str, plans: List[GptsPlan]):
        """Append plans."""
        self.plans_cache[conv_id].extend(plans)
        await blocking_func_to_async(
            self._executor, self.plans_memory.batch_save, plans
        )

    async def update_plan(self, conv_id: str, plan: GptsPlan):
        logger.info(f"update_plan:{conv_id},{plan}")
        """Update plans."""
        plans: List[GptsPlan] = await self.get_plans(conv_id)
        new_plans = []
        for item in plans:
            if item.task_uid == plan.task_uid:
                item.state = plan.state
                item.retry_times = plan.retry_times
                item.agent_model = plan.agent_model
                item.result = plan.result
            new_plans.append(item)
            await blocking_func_to_async(
                self._executor,
                self.plans_memory.update_task,
                conv_id,
                plan.sub_task_id,
                plan.state,
                plan.retry_times,
                model=plan.agent_model,
                result=plan.result,
            )
            logger.info(f"update_plan {conv_id}:{item.task_uid} sucess！")
        self.plans_cache[conv_id] = new_plans

    async def get_plans(self, conv_id: str) -> List[GptsPlan]:
        """Get plans by conv_id."""
        plans = self.plans_cache[conv_id]
        return plans

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
            messages = await blocking_func_to_async(
                self._executor, self.message_memory.get_by_conv_id, conv_id=conv_id
            )

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
            messages = await blocking_func_to_async(
                self._executor, self.message_memory.get_by_conv_id, conv_id=conv_id
            )

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
