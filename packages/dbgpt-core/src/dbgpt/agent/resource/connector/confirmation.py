"""Confirmation interceptor and registry for human-in-the-loop approval flows."""

import asyncio
import dataclasses
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .catalog import ConnectorCatalog


@dataclasses.dataclass
class PendingConfirmation:
    confirm_id: str
    event: asyncio.Event
    result: Optional[bool] = None
    created_at: float = dataclasses.field(default_factory=time.monotonic)


class ConfirmationRegistry:
    def __init__(self) -> None:
        self._pending: Dict[str, PendingConfirmation] = {}

    def register(self, confirm_id: str) -> PendingConfirmation:
        pending = PendingConfirmation(
            confirm_id=confirm_id,
            event=asyncio.Event(),
        )
        self._pending[confirm_id] = pending
        return pending

    def resolve(self, confirm_id: str, approved: bool) -> bool:
        pending = self._pending.get(confirm_id)
        if pending is None:
            return False
        pending.result = approved
        pending.event.set()
        return True

    async def wait_for(self, confirm_id: str, timeout: float = 300.0) -> bool:
        pending = self._pending.get(confirm_id)
        if pending is None:
            return False
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
            return bool(pending.result)
        except asyncio.TimeoutError:
            self._pending.pop(confirm_id, None)
            return False

    def cleanup_expired(self, max_age: float = 300.0) -> None:
        now = time.monotonic()
        expired = [
            cid for cid, p in self._pending.items() if (now - p.created_at) > max_age
        ]
        for cid in expired:
            self._pending.pop(cid, None)


class ConfirmationInterceptor:
    def __init__(self, catalog: "ConnectorCatalog") -> None:
        self._catalog = catalog

    def should_confirm(
        self,
        tool_name: str,
        tool_args: dict,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if context and context.get("trigger_type") == "scheduled":
            return False
        for entry in self._catalog.list():
            if tool_name in entry.confirm_actions:
                return True
        return False

    def format_confirmation(
        self,
        tool_name: str,
        tool_args: dict,
        confirm_id: str,
    ) -> dict:
        return {
            "type": "step.confirm",
            "tool": tool_name,
            "args_summary": self._summarize_args(tool_args),
            "confirm_id": confirm_id,
            "timeout": 300,
        }

    def _summarize_args(self, tool_args: dict) -> str:
        _HIDDEN = {"password", "token", "secret", "api_key", "github_token"}
        parts: List[str] = []
        for k, v in tool_args.items():
            if k.lower() in _HIDDEN or any(s in k.lower() for s in _HIDDEN):
                parts.append(f"{k}=***")
            else:
                parts.append(f"{k}={v!r}")
        return ", ".join(parts)


_PENDING_CONFIRMATIONS: Dict[str, dict] = {}
