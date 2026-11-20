"""Durable snapshots of one ReAct turn, including disconnected streams."""

import logging
import time
from typing import Any, Callable, Optional

from dbgpt.core.interface.message import MessageStorageItem

logger = logging.getLogger(__name__)


def save_history_view(storage: Any, payload: str) -> None:
    """Replace this round's checkpoint instead of appending duplicate replies."""
    current = next(
        (
            message
            for message in reversed(getattr(storage, "messages", []))
            if message.type == "view" and message.round_index == storage.chat_order
        ),
        None,
    )
    if current is None:
        storage.add_view_message(payload)
    else:
        current.content = payload
        # StorageConversation.save_to_storage only inserts new messages. An
        # existing view needs an explicit upsert to survive a fresh DB read.
        if storage.save_message_independent:
            storage.message_storage.save_or_update(
                MessageStorageItem(storage.conv_uid, current.index, current.to_dict())
            )
    storage.save_to_storage()


class ReactHistoryCheckpoint:
    """Rate-limit progress writes; always save initial and interrupted state."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.storage: Any = None
        self.snapshot: Optional[Callable[[str], str]] = None
        self.last_saved = float("-inf")
        self.finished = False

    def bind(self, storage: Any, snapshot: Callable[[str], str]) -> None:
        self.storage, self.snapshot = storage, snapshot

    def flush(self, *, status: str = "running", force: bool = False) -> None:
        if self.finished or self.storage is None or self.snapshot is None:
            return
        now = self.clock()
        if not force and now - self.last_saved < 2:
            return
        # Back off on storage errors too; never log one error per token.
        self.last_saved = now
        try:
            save_history_view(self.storage, self.snapshot(status))
        except Exception:
            logger.exception("Failed to persist ReAct progress checkpoint")
