"""Conv-scoped pi harness runner.

One :class:`PiHarnessRunner` owns one pi RPC child per
conversation: the child is spawned lazily, reused across
runs (follow-up questions continue the same pi session
naturally), reaped after idle, and restarted once on
crash. Runs stream neutral :class:`HarnessEvent` values
and return the final assistant text.
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from ..base import (
    HarnessError,
    HarnessEvent,
    HarnessResult,
    PiProcessDeadError,
)
from .config import PiHarnessConfig
from .events import _assistant_text_from_message, map_rpc_event
from .rpc_client import PiRpcClient

logger = logging.getLogger(__name__)

StepperFn = Callable[[HarnessEvent], Awaitable[None]]


class PiHarnessRunner:
    """Run agent turns on pi over RPC.

    Lifecycle: ``run()`` spawns the child on first use; the child
    stays warm so pi keeps its own session context between runs;
    an idle reaper closes it after ``config.idle_timeout_s``.
    On unexpected child death, the *current* run transparently
    restarts once (progress summary is the caller's concern; pi
    session state carries over when session files are enabled).
    """

    def __init__(self, config: PiHarnessConfig, conv_id: str):
        self._config = config
        self._conv_id = conv_id
        self._client: Optional[PiRpcClient] = None
        self._busy = False
        self._last_active = time.monotonic()
        self._reaper_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._closed = False

    # -- introspection ----------------------------------------------

    @property
    def conv_id(self) -> str:
        return self._conv_id

    @property
    def alive(self) -> bool:
        """Whether the pi child is up."""
        return self._client is not None and self._client.alive

    # -- lifecycle ----------------------------------------------------

    async def ensure_started(self) -> PiRpcClient:
        """Spawn the pi RPC child if needed."""
        async with self._lock:
            if self._client is not None and self._client.alive:
                return self._client
            return await self._start_child()

    async def _start_child(self) -> PiRpcClient:
        config = self._config
        if config.model_api_base:
            config.prepare_agent_dir()
        command = config.resolve_command()
        logger.info(
            "pi harness[%s]: spawning %s cwd=%s agent_dir=%s",
            self._conv_id,
            command,
            config.cwd,
            config.agent_dir,
        )
        self._client = await PiRpcClient.spawn(
            command,
            cwd=config.cwd,
            env=config.build_env(),
        )
        self._last_active = time.monotonic()
        self._ensure_reaper()
        return self._client

    def _ensure_reaper(self) -> None:
        timeout = self._config.idle_timeout_s
        if timeout <= 0 or self._reaper_task:
            return
        self._reaper_task = asyncio.ensure_future(self._idle_reaper(timeout))

    async def _idle_reaper(self, timeout_s: float) -> None:
        while not self._closed:
            await asyncio.sleep(min(60.0, max(1.0, timeout_s / 4)))
            if (
                self._closed
                or self._busy
                or self._client is None
                or not self._client.alive
            ):
                if self._closed:
                    return
                continue
            if time.monotonic() - self._last_active >= timeout_s:
                logger.info(
                    "pi harness[%s]: idle, reaping child",
                    self._conv_id,
                )
                await self.dispose()
                return

    async def dispose(self) -> None:
        """Close the pi child and stop background tasks."""
        self._closed = True
        self._reaper_task = None
        if self._client:
            await self._client.close()
            self._client = None

    # -- run -----------------------------------------------------------

    async def run(
        self,
        prompt: str,
        on_event: Optional[StepperFn] = None,
        timeout_s: Optional[float] = None,
    ) -> HarnessResult:
        """Run one prompt to settlement.

        Streams mapped events through ``on_event`` and returns
        the final text. A dead child triggers exactly one
        transparent respawn-and-retry.
        """
        timeout = timeout_s or self._config.run_timeout_s
        if timeout <= 0:
            timeout = None
        self._last_active = time.monotonic()
        try:
            return await self._run_once(prompt, on_event, timeout)
        except (PiProcessDeadError, HarnessError) as e:
            if not self._is_process_dead(e):
                raise
            logger.warning(
                "pi harness[%s]: child died (%s); restarting once",
                self._conv_id,
                e,
            )
            await self.dispose()
            self._last_active = time.monotonic()
            return await self._run_once(prompt, on_event, timeout)

    @staticmethod
    def _is_process_dead(err: Exception) -> bool:
        return isinstance(err, PiProcessDeadError) or (
            isinstance(err, HarnessError) and "process is not running" in str(err)
        )

    async def _run_once(
        self,
        prompt: str,
        on_event: Optional[StepperFn],
        timeout: Optional[float],
    ) -> HarnessResult:
        client = await self.ensure_started()
        self._busy = True
        round_no = 0
        final_text = ""
        usage: Dict[str, Any] = {}
        error: Optional[str] = None
        aborted = False
        raise_cancelled = False
        queue = client.subscribe()
        try:
            # Subscribed before the prompt goes out, so a fast
            # completion cannot be missed.
            resp = await client.command(
                {"type": "prompt", "message": prompt},
                timeout_s=self._config.command_timeout_s,
            )
            disposition = (resp.get("data") or {}).get("disposition", "started")
            logger.info(
                "pi harness[%s]: prompt accepted, disposition=%s",
                self._conv_id,
                disposition,
            )
            if disposition == "handled":
                # An extension consumed the prompt: no run and no
                # agent_settled will follow.
                return HarnessResult(rounds=0)
            loop = asyncio.get_event_loop()
            deadline = loop.time() + timeout if timeout else None
            saw_settled = False
            while not saw_settled:
                if deadline is not None:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        error = f"pi run timeout ({timeout}s)"
                        break
                    record = await self._get_event(queue, remaining)
                else:
                    record = await self._get_event(queue, None)
                if record is None:
                    error = error or (client.exit_error or "pi process ended")
                    break
                etype = record.get("type")
                # Key lifecycle events at INFO so failures are
                # diagnosable from logs without a debugger.
                if etype in (
                    "turn_start",
                    "turn_end",
                    "message_start",
                    "message_end",
                    "agent_settled",
                    "agent_end",
                    "error",
                    "auto_retry_start",
                    "auto_retry_end",
                ):
                    preview = str(record)[:200]
                    logger.info(
                        "pi harness[%s]: event %s %s",
                        self._conv_id,
                        etype,
                        preview,
                    )
                if etype == "turn_start":
                    round_no += 1
                elif etype == "message_end":
                    message = record.get("message") or {}
                    if message.get("role") == "assistant":
                        text = _assistant_text_from_message(message)
                        logger.info(
                            "pi harness[%s]: message_end assistant "
                            "content=%s stopReason=%s extracted=%d chars",
                            self._conv_id,
                            str(message.get("content"))[:200],
                            message.get("stopReason"),
                            len(text),
                        )
                        if text.strip():
                            final_text = text
                elif etype == "message_update":
                    u = record.get("usage") or {}
                    if isinstance(u, dict) and u.get("totalTokens"):
                        usage = u
                elif etype in ("agent_settled", "agent_end"):
                    saw_settled = True
                    aborted = bool(record.get("aborted", False))
                await self._emit(on_event, record, round_no)
        except asyncio.CancelledError:
            raise_cancelled = True
        except (PiProcessDeadError, HarnessError, asyncio.TimeoutError) as e:
            error = str(e)
        finally:
            client.unsubscribe(queue)
            if (error or raise_cancelled) and self.alive:
                await self._abort_quietly()
            self._busy = False
            self._last_active = time.monotonic()
        if raise_cancelled:
            raise asyncio.CancelledError()
        return HarnessResult(
            final_text=final_text,
            aborted=aborted,
            error=error,
            rounds=round_no,
            usage=usage,
        )

    @staticmethod
    async def _get_event(queue, remaining: Optional[float]):
        if remaining is None:
            return await queue.get()
        return await asyncio.wait_for(queue.get(), timeout=remaining)

    @staticmethod
    async def _emit(
        on_event: Optional[StepperFn],
        record: Dict[str, Any],
        round_no: int,
    ) -> None:
        if on_event is None:
            return
        try:
            ev = map_rpc_event(record, round_no)
        except Exception as e:  # mapping bugs must not kill runs
            logger.warning("pi harness: event mapping error: %s", e)
            return
        if ev is None:
            return
        try:
            await on_event(ev)
        except Exception as e:  # consumer bugs must not kill runs
            logger.warning("pi harness: on_event consumer error: %s", e)

    async def _abort_quietly(self) -> None:
        client = self._client
        if client is None or not client.alive:
            return
        try:
            await client.command(
                {"type": "abort"},
                timeout_s=self._config.command_timeout_s,
            )
        except Exception as e:  # pragma: no cover - best effort
            logger.debug("pi abort failed: %s", e)

    # -- steering ---------------------------------------------------

    async def steer(self, text: str) -> None:
        """Queue a steering message for a running turn."""
        client = await self.ensure_started()
        await client.command(
            {"type": "steer", "message": text},
            timeout_s=self._config.command_timeout_s,
        )

    async def abort(self) -> None:
        """Abort the active run."""
        client = await self.ensure_started()
        await client.command(
            {"type": "abort"},
            timeout_s=self._config.command_timeout_s,
        )
