"""Async JSONL client for pi's RPC mode.

Implements the child-process half of pi's RPC protocol
(``pi --mode rpc``): strict LF-framed JSONL on stdin/stdout,
commands correlated by ``id``, session events fanned out to
subscribers.

Protocol facts this client relies on (pi docs, ``rpc.md`` /
``json.md``):

- A successful ``prompt`` response only means the prompt was
  accepted/queued/handled — completion is signaled by the
  ``agent_settled`` event, *not* ``agent_end``;
- stdout is reserved for protocol records (diagnostics go to
  stderr) and must be read continuously to avoid stalling pi;
- records split on LF only (Python's ``readline`` is safe:
  it does not split on U+2028/2029, which are valid inside
  JSON strings);
- closing the child's stdin requests orderly shutdown.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from ..base import HarnessError, PiProcessDeadError

logger = logging.getLogger(__name__)


@dataclass
class _PendingCommand:
    future: "asyncio.Future[Dict[str, Any]]"
    command: str = ""


class PiRpcClient:
    """One pi RPC child process.

    Transport-only: it knows about framing and response
    correlation, not about agent semantics.
    """

    def __init__(self, process: "asyncio.subprocess.Process"):
        self._process = process
        self._pending: Dict[str, _PendingCommand] = {}
        self._event_queues: List["asyncio.Queue[Optional[dict]]"] = []
        self._closed = False
        self._reader_task: Optional[asyncio.Task] = None
        self._exit_error: Optional[str] = None

    # -- lifecycle --------------------------------------------------

    @classmethod
    async def spawn(
        cls,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> "PiRpcClient":
        """Spawn a pi RPC child and start its stdout reader."""
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=2**22,  # 4 MiB per record is plenty
        )
        client = cls(proc)
        client._reader_task = asyncio.ensure_future(client._read_loop())
        return client

    @property
    def alive(self) -> bool:
        """Whether the child process is still running."""
        return self._process.returncode is None and not self._closed

    @property
    def exit_error(self) -> Optional[str]:
        """Description of an unexpected child exit, when known."""
        return self._exit_error

    async def close(self, grace_s: float = 5.0) -> None:
        """Close stdin (orderly shutdown) and reap the child."""
        if self._closed:
            return
        self._closed = True
        # Drain stderr eagerly so pi diagnostics are always
        # visible in the server log, even for a clean exit.
        if self._process.stderr:
            try:
                stderr = await asyncio.wait_for(
                    self._process.stderr.read(), timeout=1.0
                )
                if stderr:
                    logger.info(
                        "pi rpc stderr: %s",
                        stderr[-800:].decode("utf-8", "replace"),
                    )
            except Exception:
                pass
        try:
            if self.alive and self._process.stdin:
                self._process.stdin.close()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("pi stdin close failed: %s", e)
        try:
            await asyncio.wait_for(self._process.wait(), timeout=grace_s)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()
        self._fail_pending("pi process closed")
        self._broadcast(None)  # ends subscriber iterators
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: B014
                pass

    # -- commands ---------------------------------------------------

    async def command(
        self,
        record: Dict[str, Any],
        timeout_s: float = 60.0,
    ) -> Dict[str, Any]:
        """Send one command record, await its correlated response.

        Raises :class:`HarnessError` when the response carries
        ``success: false`` or the child died before answering.
        """
        record = dict(record)
        req_id = record.get("id") or uuid.uuid4().hex
        record["id"] = req_id
        if not self.alive:
            raise PiProcessDeadError(self._exit_error or "pi process is not running")
        loop = asyncio.get_event_loop()
        fut: "asyncio.Future[Dict[str, Any]]" = loop.create_future()
        self._pending[req_id] = _PendingCommand(fut, str(record.get("type", "")))
        self._write(record)
        try:
            resp = await asyncio.wait_for(fut, timeout=timeout_s)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise HarnessError(
                f"pi command timeout ({timeout_s}s): {record.get('type')}"
            )
        if not resp.get("success", False):
            raise HarnessError(f"pi command failed: {resp.get('error', 'unknown')}")
        return resp

    # -- event subscription ------------------------------------------

    def subscribe(self) -> "asyncio.Queue[Optional[dict]]":
        """Register an event queue; terminate with ``None``."""
        q: "asyncio.Queue[Optional[dict]]" = asyncio.Queue()
        self._event_queues.append(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[Optional[dict]]") -> None:
        """Remove a previously registered event queue."""
        try:
            self._event_queues.remove(q)
        except ValueError:
            pass

    # -- internals ----------------------------------------------------

    def _write(self, record: Dict[str, Any]) -> None:
        assert self._process.stdin is not None
        data = json.dumps(record, ensure_ascii=False).encode("utf-8")
        self._process.stdin.write(data + b"\n")

    async def _read_loop(self) -> None:
        assert self._process.stdout is not None
        proc = self._process
        try:
            while not proc.stdout.at_eof():
                line = await proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning("pi rpc: bad record dropped: %s", e)
                    continue
                self._dispatch(record)
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("pi rpc reader crashed: %s", e)
        if proc.returncode is None:
            # stdout hit EOF while the process is still alive:
            # treat as dead to unblock waiters.
            proc.kill()
        rc = await proc.wait()
        if rc != 0 and not self._closed:
            stderr = b""
            if proc.stderr:
                try:
                    stderr = await asyncio.wait_for(proc.stderr.read(), timeout=2.0)
                except Exception:  # pragma: no cover
                    pass
            self._exit_error = (
                f"pi exited code={rc}: {stderr[-500:].decode('utf-8', 'replace')}"
            )
            logger.error(
                "pi rpc: child exited code=%s stderr=%s",
                rc,
                self._exit_error,
            )
        self._fail_pending(self._exit_error or "pi process died")
        self._broadcast(None)

    def _dispatch(self, record: Dict[str, Any]) -> None:
        if record.get("type") == "response" and record.get("id"):
            fut_holder = self._pending.pop(str(record["id"]), None)
            if fut_holder and not fut_holder.future.done():
                fut_holder.future.set_result(record)
            elif fut_holder is None:
                logger.debug(
                    "pi rpc: response for unknown id: %s",
                    record.get("id"),
                )
            return
        self._broadcast(record)

    def _broadcast(self, record: Optional[dict]) -> None:
        for q in list(self._event_queues):
            q.put_nowait(record)

    def _fail_pending(self, reason: str) -> None:
        for holder in list(self._pending.values()):
            if not holder.future.done():
                fut_holder = holder
                fut_holder.future.set_exception(PiProcessDeadError(reason))
        self._pending.clear()

    # -- convenience --------------------------------------------------

    async def iter_events(self) -> AsyncIterator[dict]:
        """Iterate session events until the child ends or closes."""
        q = self.subscribe()
        try:
            while True:
                record = await q.get()
                if record is None:
                    break
                yield record
        finally:
            self.unsubscribe(q)
