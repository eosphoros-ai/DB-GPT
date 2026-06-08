"""ChatReplayRunner — execution core for scheduled chat-replay tasks.

Replays a conversation snapshot by invoking the ReAct agent stream
**in-process** (no HTTP self-call), then records the run result
(success / failed / timeout) in the run table.

The module-level ``run_scheduled_task`` function is the entry point
registered with APScheduler.  It creates a fresh ``ChatReplayRunner``
instance on every invocation so that the callable stored in the
scheduler job store is a plain module-level function (which **can** be
pickled by SQLAlchemyJobStore), not a bound method whose owner holds
unpicklable SQLAlchemy sessions.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from ..dao.run_dao import ScheduledRunDao
from ..dao.task_dao import ScheduledTaskDao

logger = logging.getLogger(__name__)


# ── Module-level entry point for APScheduler ──────────────────────────


async def run_scheduled_task(task_id: str) -> None:
    """APScheduler job callback — creates a runner and delegates.

    This **must** be a module-level function (not a bound method) so
    that APScheduler's SQLAlchemyJobStore can pickle the job state.
    The runner is instantiated fresh on each invocation to avoid
    holding stale SQLAlchemy sessions across runs.
    """
    runner = ChatReplayRunner()
    await runner.replay_chat_task(task_id)


_SUMMARY_MAX = 1024
_ERROR_MAX = 2000


class ChatReplayRunner:
    """Execute a scheduled chat-replay task.

    Called by the scheduler at cron time to replay a conversation by
    invoking the ReAct agent stream directly (in the same process) and
    recording the result in the run table.

    Args:
        request_timeout: Timeout in seconds for a single replay run.
    """

    def __init__(self, request_timeout: float = 600.0):
        self._timeout = request_timeout
        self._task_dao = ScheduledTaskDao()
        self._run_dao = ScheduledRunDao()

    async def replay_chat_task(self, task_id: str) -> None:
        """Replay a chat task by task_id.

        This is the callback invoked by the scheduler. It must never
        raise an exception — all errors are caught and recorded in the
        run table.

        Args:
            task_id: The UUID of the scheduled task to replay.
        """
        run_id = str(uuid.uuid4())
        new_conv_uid = str(uuid.uuid4())
        started_at = datetime.now()

        # 1. Create a run record with status='running'
        self._run_dao.create(
            {
                "run_id": run_id,
                "task_id": task_id,
                "started_at": started_at,
                "status": "running",
            }
        )

        try:
            # 2. Look up the task
            task = self._task_dao.get_one({"task_id": task_id})
            if task is None:
                self._fail(run_id, "task not found", new_conv_uid)
                return
            if not task.get("enabled", False):
                self._fail(run_id, "task disabled", new_conv_uid)
                return

            # 3. Rebuild the conversation request from the frozen snapshot.
            #    Use a fresh conv_uid so each run is its own dialog.
            payload = json.loads(task["payload_json"])
            payload["conv_uid"] = new_conv_uid
            payload["user_name"] = task.get("user_name")
            payload.pop("version", None)  # internal field, not a ConversationVo key

            # 4. Replay in-process with a hard timeout
            final_texts, step_texts, artifact_count = await asyncio.wait_for(
                self._run_agent_stream(payload),
                timeout=self._timeout,
            )

            # 5. Success — prefer final text, fall back to step texts
            summary_source = final_texts if final_texts else step_texts
            self._run_dao.update(
                {"run_id": run_id},
                {
                    "status": "success",
                    "finished_at": datetime.now(),
                    "result_summary": self._summarize(summary_source, artifact_count),
                    "output_conv_uid": new_conv_uid,
                },
            )
        except asyncio.TimeoutError:
            logger.warning("scheduled task %s timed out", task_id)
            self._run_dao.update(
                {"run_id": run_id},
                {
                    "status": "timeout",
                    "finished_at": datetime.now(),
                    "error_message": f"execution exceeded {self._timeout}s",
                    "output_conv_uid": new_conv_uid,
                },
            )
        except Exception as exc:
            logger.exception("scheduled task %s failed", task_id)
            self._run_dao.update(
                {"run_id": run_id},
                {
                    "status": "failed",
                    "finished_at": datetime.now(),
                    "error_message": str(exc)[:_ERROR_MAX],
                    "output_conv_uid": new_conv_uid,
                },
            )

    async def _run_agent_stream(self, payload: dict):
        """Invoke the ReAct agent stream in-process and collect outputs.

        Returns:
            (final_texts, step_texts, artifact_count)
        """
        # Lazy import to avoid a top-level dbgpt-serve -> dbgpt-app cycle.
        # This matches the project convention (see dbgpt_serve/agent/...).
        from dbgpt_app.openapi.api_v1.agentic_data_api import _react_agent_stream
        from dbgpt_app.openapi.api_view_model import ConversationVo

        dialogue = ConversationVo(**payload)

        final_texts: List[str] = []
        step_texts: List[str] = []
        artifact_count = 0

        async for line in _react_agent_stream(dialogue):
            parsed = self._parse_sse(line)
            if parsed is None:
                continue
            etype = parsed.get("type")
            if etype == "final":
                content = parsed.get("content")
                if isinstance(content, str):
                    final_texts.append(content)
            elif etype == "step.chunk":
                otype = parsed.get("output_type")
                content = parsed.get("content")
                if otype == "text" and isinstance(content, str):
                    step_texts.append(content)
                elif otype in ("code", "table", "chart", "markdown", "json"):
                    artifact_count += 1
            # Other types (step.start/step.done/step.meta/step.thought/
            # done/react-agent) are ignored.

        return final_texts, step_texts, artifact_count

    def _fail(self, run_id: str, message: str, conv_uid: str) -> None:
        """Record a failed run with the given error message."""
        self._run_dao.update(
            {"run_id": run_id},
            {
                "status": "failed",
                "finished_at": datetime.now(),
                "error_message": message[:_ERROR_MAX],
                "output_conv_uid": conv_uid,
            },
        )

    @staticmethod
    def _parse_sse(line: str) -> Optional[dict]:
        """Parse a single SSE line and return the JSON payload.

        Returns None for empty lines, non-data lines, or malformed JSON.
        """
        if not line or not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data:
            return None
        try:
            return json.loads(data)
        except Exception:
            return None

    @staticmethod
    def _summarize(text_chunks: List[str], artifact_count: int) -> str:
        """Build a summary string, truncated to _SUMMARY_MAX chars."""
        joined = "".join(text_chunks)
        if artifact_count > 0:
            suffix = f" [artifacts: {artifact_count}]"
            max_text = _SUMMARY_MAX - len(suffix)
            if len(joined) > max_text:
                joined = joined[:max_text]
            return (joined + suffix)[:_SUMMARY_MAX]
        if len(joined) > _SUMMARY_MAX:
            joined = joined[:_SUMMARY_MAX]
        return joined
