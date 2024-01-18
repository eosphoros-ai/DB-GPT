from __future__ import annotations

import asyncio
import json
import logging
from asyncio import Queue, QueueEmpty, wait_for
from datetime import datetime
from enum import Enum
from json import JSONDecodeError
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

logger = logging.getLogger(__name__)


class PluginStorageType(Enum):
    Git = "git"
    Oss = "oss"


class ApiTagType(Enum):
    API_VIEW = "dbgpt_view"
    API_CALL = "dbgpt_call"


class Status(Enum):
    TODO = "todo"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    FAILED = "failed"
    COMPLETE = "complete"


class GptsMessage:
    """Gpts message"""

    conv_id: str
    sender: str

    receiver: str
    role: str
    content: str
    rounds: Optional[int]
    current_gogal: str = None
    context: Optional[str] = None
    review_info: Optional[str] = None
    action_report: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime = datetime.utcnow
    updated_at: datetime = datetime.utcnow

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> GptsMessage:
        return GptsMessage(
            conv_id=d["conv_id"],
            sender=d["sender"],
            receiver=d["receiver"],
            role=d["role"],
            content=d["content"],
            rounds=d["rounds"],
            model_name=d["model_name"],
            current_gogal=d["current_gogal"],
            context=d["context"],
            review_info=d["review_info"],
            action_report=d["action_report"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )


class MessageQueue(BaseModel):
    """Message queue which supports asynchronous updates."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _queue: Queue = PrivateAttr(default_factory=Queue)

    def pop(self) -> GptsMessage | None:
        """Pop one message from the queue."""
        try:
            item = self._queue.get_nowait()
            if item:
                self._queue.task_done()
            return item
        except QueueEmpty:
            return None

    def pop_all(self) -> List[GptsMessage]:
        """Pop all messages from the queue."""
        ret = []
        while True:
            msg = self.pop()
            if not msg:
                break
            ret.append(msg)
        return ret

    def push(self, msg: GptsMessage):
        """Push a message into the queue."""
        self._queue.put_nowait(msg)

    def empty(self):
        """Return true if the queue is empty."""
        return self._queue.empty()

    async def dump(self) -> str:
        """Convert the `MessageQueue` object to a json string."""
        if self.empty():
            return "[]"

        lst = []
        msgs = []
        try:
            while True:
                item = await wait_for(self._queue.get(), timeout=1.0)
                if item is None:
                    break
                msgs.append(item)
                lst.append(item.dump())
                self._queue.task_done()
        except asyncio.TimeoutError:
            logger.debug("Queue is empty, exiting...")
        finally:
            for m in msgs:
                self._queue.put_nowait(m)
        return json.dumps(lst, ensure_ascii=False)

    @staticmethod
    def load(data) -> "MessageQueue":
        """Convert the json string to the `MessageQueue` object."""
        queue = MessageQueue()
        try:
            lst = json.loads(data)
            for i in lst:
                msg = GptsMessage.load(i)
                queue.push(msg)
        except JSONDecodeError as e:
            logger.warning(f"JSON load failed: {data}, error:{e}")

        return queue
