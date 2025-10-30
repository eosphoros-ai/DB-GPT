import asyncio
import logging
from typing import List, Optional

import lyricore as lc

from ...vis.vis_converter import DefaultVisConverter, VisProtocolConverter
from .. import ActionOutput
from .agent import AgentStateTaskResult
from .memory.gpts import (
    DefaultGptsMessageMemory,
    DefaultGptsPlansMemory,
    GptsMemory,
    GptsMessage,
    GptsMessageMemory,
    GptsPlan,
    GptsPlansMemory,
)

logger = logging.getLogger(__name__)


class MemoryActor:
    """An actor that manages memory for agents."""

    def __init__(
        self,
        plans_memory: Optional[GptsPlansMemory] = None,
        message_memory: Optional[GptsMessageMemory] = None,
    ):
        """Create a memory to store plans and messages."""
        self._gpts_memory = GptsMemory(
            plans_memory=plans_memory
            if plans_memory is not None
            else DefaultGptsPlansMemory(),
            message_memory=message_memory
            if message_memory is not None
            else DefaultGptsMessageMemory(),
        )

    async def append_message(
        self,
        conv_id: str,
        message: GptsMessage,
        incremental: bool = False,
        save_db: bool = True,
    ):
        await self._gpts_memory.append_message(
            conv_id, message, incremental=incremental, save_db=save_db
        )

    async def init(
        self,
        conv_id: str,
        enable_vis_message: bool = True,
        history_messages: Optional[List[GptsMessage]] = None,
        vis_converter: Optional[VisProtocolConverter] = None,
        start_round: int = 0,
    ):
        self._gpts_memory.init(
            conv_id=conv_id,
            enable_vis_message=enable_vis_message,
            history_messages=history_messages,
            vis_converter=vis_converter,
            start_round=start_round,
        )

    async def clear(self, conv_id: str):
        # TODO: run in separate thread
        self._gpts_memory.clear(conv_id)

    async def complete(self, conv_id: str):
        await self._gpts_memory.complete(conv_id)

    async def push_message(self, conv_id: str, temp_msg: Optional[str] = None):
        await self._gpts_memory.push_message(conv_id, temp_msg)

    async def get_agent_history_memory(
        self, conv_id: str, agent_role: str
    ) -> List[ActionOutput]:
        return await self._gpts_memory.get_agent_history_memory(conv_id, agent_role)

    async def get_queue_messages(self, conv_id: str):
        queue = self._gpts_memory.queue(conv_id)
        if not queue:
            return {"break": True, "messages": []}
        # item = await queue.get()
        try:
            item = queue.get_nowait()
            if item == "[DONE]":
                queue.task_done()
                return {"break": True, "messages": []}
            else:
                return {"break": False, "messages": [item]}
        except asyncio.QueueEmpty:
            return {"break": False, "messages": []}

    async def get_messages(self, conv_id: str) -> List[GptsMessage]:
        return await self._gpts_memory.get_messages(conv_id)

    async def app_link_chat_message(self, conv_id: str):
        return await self._gpts_memory.app_link_chat_message(conv_id)

    async def get_by_conv_id_and_num(
        self, conv_id: str, task_ids: List[str]
    ) -> List[GptsPlan]:
        # TODO: run in separate thread
        return self._gpts_memory.plans_memory.get_by_conv_id_and_num(conv_id, task_ids)

    async def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        # TODO: run in separate thread
        return self._gpts_memory.plans_memory.get_by_conv_id(conv_id)

    async def complete_task(self, conv_id: str, task_id: str, result: str) -> None:
        # TODO: run in separate thread
        return self._gpts_memory.plans_memory.complete_task(conv_id, task_id, result)

    async def update_task(
        self,
        conv_id: str,
        task_id: str,
        state: str,
        retry_times: int,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        # TODO: run in separate thread
        return self._gpts_memory.plans_memory.update_task(
            conv_id, task_id, state, retry_times, agent, model, result
        )

    async def remove_by_conv_id(self, conv_id: str) -> None:
        # TODO: run in separate thread
        return self._gpts_memory.plans_memory.remove_by_conv_id(conv_id)

    async def batch_save(self, plans: List[GptsPlan]) -> None:
        # TODO: run in separate thread
        return self._gpts_memory.plans_memory.batch_save(plans)


class ActorGptsMemory:
    """An actor that manages memory for agents."""

    def __init__(
        self,
        actor_ref: lc.ActorRef,
    ):
        """Create a memory to store plans and messages."""
        self.actor_ref = actor_ref
        # TODO: use the vis converter from memory
        self._vis_converter: VisProtocolConverter = DefaultVisConverter()

    async def append_message(
        self,
        conv_id: str,
        message: GptsMessage,
        incremental: bool = False,
        save_db: bool = True,
    ):
        await self.actor_ref.append_message.ask(conv_id, message, incremental, save_db)

    async def init(
        self,
        conv_id: str,
        enable_vis_message: bool = True,
        history_messages: Optional[List[GptsMessage]] = None,
        vis_converter: Optional[VisProtocolConverter] = None,
        start_round: int = 0,
    ):
        await self.actor_ref.init.ask(
            conv_id, enable_vis_message, history_messages, vis_converter, start_round
        )

    async def clear(self, conv_id: str):
        await self.actor_ref.clear.ask(conv_id)

    async def complete(self, conv_id: str):
        await self.actor_ref.complete.ask(conv_id)

    async def push_message(self, conv_id: str, temp_msg: Optional[str] = None):
        await self.actor_ref.push_message.ask(conv_id, temp_msg)

    async def get_agent_history_memory(
        self, conv_id: str, agent_role: str
    ) -> List[ActionOutput]:
        return await self.actor_ref.get_agent_history_memory.ask(conv_id, agent_role)
        # return []

    async def get_messages(self, conv_id: str) -> List[GptsMessage]:
        return await self.actor_ref.get_messages.ask(conv_id)

    async def app_link_chat_message(self, conv_id: str):
        return await self.actor_ref.app_link_chat_message.ask(conv_id)

    @property
    def vis_converter(self):
        """Return the vis converter"""
        return self._vis_converter

    async def stream_messages(
        self,
        conv_id: str,
    ):
        while True:
            msg = await self.actor_ref.get_queue_messages.ask(conv_id)
            break_loop = msg.get("break", True)
            logger.debug(f"stream_messages: {msg}")
            if break_loop:
                break
            messages = msg.get("messages", [])
            for m in messages:
                yield m
            if not messages:
                await asyncio.sleep(0.1)
            else:
                await asyncio.sleep(0.005)

    async def get_by_conv_id_and_num(
        self, conv_id: str, task_ids: List[str]
    ) -> List[GptsPlan]:
        return await self.actor_ref.get_by_conv_id_and_num.ask(conv_id, task_ids)

    async def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        return await self.actor_ref.get_by_conv_id.ask(conv_id)

    async def complete_task(self, conv_id: str, task_id: str, result: str) -> None:
        return await self.actor_ref.complete_task.ask(conv_id, task_id, result)

    async def update_task(
        self,
        conv_id: str,
        task_id: str,
        state: str,
        retry_times: int,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        return await self.actor_ref.update_task.ask(
            conv_id, task_id, state, retry_times, agent, model, result
        )

    async def remove_by_conv_id(self, conv_id: str) -> None:
        return await self.actor_ref.remove_by_conv_id.ask(conv_id)

    async def batch_save(self, plans: List[GptsPlan]) -> None:
        return await self.actor_ref.batch_save.ask(plans)


class AgentActorMonitor:
    """An actor that manages memory for agents."""

    def __init__(self, gpts_memory: ActorGptsMemory):
        """Create a memory to store plans and messages."""
        self.gpts_memory = gpts_memory

    @lc.on(AgentStateTaskResult)
    async def handle_agent_state_message(self, message: AgentStateTaskResult, ctx):
        if isinstance(message, AgentStateTaskResult):
            if message.is_success:
                logger.info(
                    f"Agent {message.role}({message.name}) completed task successfully."
                )
            else:
                logger.warning(
                    f"Agent {message.role}({message.name}) failed to complete task: {message.result}"
                )
            await self.gpts_memory.complete(message.conv_id)
