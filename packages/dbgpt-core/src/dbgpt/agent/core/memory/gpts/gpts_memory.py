"""GPTs memory."""

import asyncio
import json
import logging
from asyncio import Queue
from collections import defaultdict
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

from dbgpt.util.executor_utils import blocking_func_to_async

from .....util.id_generator import IdGenerator
from .....vis.vis_converter import DefaultVisConverter, VisProtocolConverter
from ...action.base import ActionOutput
from .base import GptsMessage, GptsMessageMemory, GptsPlan, GptsPlansMemory
from .default_gpts_memory import DefaultGptsMessageMemory, DefaultGptsPlansMemory

logger = logging.getLogger(__name__)


class GptsMemory:
    """GPTs memory."""

    def __init__(
        self,
        plans_memory: Optional[GptsPlansMemory] = None,
        message_memory: Optional[GptsMessageMemory] = None,
        executor: Optional[Executor] = None,
        vis_converter: Optional[VisProtocolConverter] = None,
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
        self.start_round_map: defaultdict = defaultdict(int)
        self._vis_converter: VisProtocolConverter = (
            vis_converter if vis_converter else DefaultVisConverter()
        )
        self.vis_converter_map: defaultdict = defaultdict(Any)

    def vis_converter(self, agent_conv_id: str):
        """Return the vis converter"""
        if agent_conv_id in self.vis_converter_map:
            return self.vis_converter_map.get(agent_conv_id)
        return self._vis_converter

    def init_agent_converter(self, agent_conv_id: str, converter: VisProtocolConverter):
        self.vis_converter_map[agent_conv_id] = converter

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
        history_messages: Optional[List[GptsMessage]] = None,
        vis_converter: Optional[VisProtocolConverter] = None,
        start_round: int = 0,
    ):
        """Gpt memory init."""
        self.channels[conv_id] = asyncio.Queue()
        if history_messages:
            self._cache_messages(conv_id, history_messages)

        self.start_round_map[conv_id] = start_round
        self._message_rounds_generator[conv_id] = IdGenerator(start_round + 1)
        self.init_agent_converter(conv_id, vis_converter)

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
        ## 消息可视化布局转换
        vis_view = await self.vis_converter(conv_id).final_view(
            messages=messages,
            plans=await self.get_plans(conv_id=conv_id),
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
        """Get all persistent messages that have been converted through the visualization protocol(excluding the part that is currently being streamed.)"""  # noqa: E501
        ## 消息数据流准备
        messages = await self.get_messages(conv_id)
        start_round = (
            self.start_round_map[conv_id] if conv_id in self.start_round_map else 0
        )
        messages = messages[start_round:]

        ## merge messages
        messages = self._merge_messages(messages)
        ## 消息可视化布局转换
        vis_view = await self.vis_converter(conv_id).visualization(
            messages=messages,
            # plans=await self.get_plans(conv_id=conv_id),
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
    ):
        """Append message."""
        # Add and update messages based on message_id
        # Cache messages
        self._cache_messages(conv_id, [message])
        # Message persistence storage
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

        return messages

    async def get_agent_messages(self, conv_id: str, agent: str) -> List[GptsMessage]:
        """Get agent messages."""
        gpt_messages = await self.get_messages(conv_id)
        result = []
        for gpt_message in gpt_messages:
            if gpt_message.sender == agent or gpt_message.receiver == agent:
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

    async def get_plans(self, conv_id: str) -> List[GptsPlan]:
        """Get plans by conv_id."""
        plans = self.plans_cache[conv_id]
        if not plans:
            plans = await blocking_func_to_async(
                self._executor, self.plans_memory.get_by_conv_id, conv_id
            )
        return plans
