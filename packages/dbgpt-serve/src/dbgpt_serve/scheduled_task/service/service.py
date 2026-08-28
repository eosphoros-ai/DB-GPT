"""ScheduledTaskService — business orchestration layer.

Orchestrates DB writes and scheduler job management with dual-write
consistency. If scheduler.add_job fails after DB write, the DB row
is rolled back (deleted).

Payload v2 file freezing: when ``payload.ext_info`` carries session
``file_ids``, creation copies them into the task scope through the injected
session file registry *before* persistence, so the stored payload only ever
contains task-scoped IDs (never session IDs, never a ``file_path``). Any
later DB/scheduler failure runs a compensating delete of the copied files;
a copy failure writes neither the task row nor the scheduler job.
"""

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from dbgpt_serve.session_file.domain import parse_file_input

from ..api.schemas import (
    ChatReplayPayload,
    CreateTaskRequest,
    RunResponse,
    TaskResponse,
    UpdateTaskRequest,
)
from ..dao.run_dao import ScheduledRunDao
from ..dao.task_dao import ScheduledTaskDao
from .chat_replay_runner import run_scheduled_task

logger = logging.getLogger(__name__)


def _validate_cron(cron_expression: str) -> None:
    """Validate a cron expression using APScheduler CronTrigger.

    Args:
        cron_expression: A 5-field or 6-field cron expression.

    Raises:
        ValueError: If the expression is invalid.
    """
    from apscheduler.triggers.cron import CronTrigger

    parts = cron_expression.strip().split()
    try:
        if len(parts) == 6:
            s, m, h, dom, mon, dow = parts
            CronTrigger(
                second=s,
                minute=m,
                hour=h,
                day=dom,
                month=mon,
                day_of_week=dow,
            )
        elif len(parts) == 5:
            CronTrigger.from_crontab(cron_expression)
        else:
            raise ValueError(f"Invalid cron expression: {cron_expression}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid cron expression: {cron_expression}: {e}")


class ScheduledTaskService:
    """Orchestrates DB writes and scheduler job management.

    Core invariant: DB row and scheduler job must always be in sync.
    If scheduler.add_job fails, the DB row must be rolled back.

    Args:
        scheduler: A TaskScheduler instance (or mock).
        runner_callable: The callable to execute when a job fires.
        resource_validator: Optional callable that validates payload
            resources before creating a task. Raises ValueError on
            validation failure.
        session_file_registry: Optional session file registry used to freeze
            ``payload.ext_info.file_ids`` into the task scope on create.
            Injected through the Serve layer (constructor), never looked up
            as a global, so tests can substitute a double.
    """

    def __init__(
        self,
        scheduler=None,
        runner_callable: Optional[Callable] = None,
        resource_validator: Optional[Callable] = None,
        session_file_registry: Optional[Any] = None,
    ):
        self._scheduler = scheduler
        # Use the module-level run_scheduled_task by default so that
        # APScheduler's SQLAlchemyJobStore can pickle the job state.
        # The parameter is kept for backward compatibility / testing.
        self._runner = runner_callable or run_scheduled_task
        self._resource_validator = resource_validator
        self._session_file_registry = session_file_registry
        self._task_dao = ScheduledTaskDao()
        self._run_dao = ScheduledRunDao()

    async def create_task(
        self,
        request: CreateTaskRequest,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
    ) -> TaskResponse:
        """Create a scheduled task (freeze files + DB + scheduler write).

        Steps:
            1. Validate cron expression
            2. Validate referenced resources (if validator injected)
            3. Generate task_id (UUID) — before the file freeze, since the
               copy targets the task scope keyed by this id
            4. Freeze payload files: copy ``ext_info.file_ids`` into the
               task scope and keep only task-scoped IDs (copy failure =>
               nothing is written)
            5. Write DB row (compensate frozen files on failure)
            6. Add scheduler job (rollback DB + frozen files on failure)
            7. Return TaskResponse

        Args:
            request: The creation request.
            user_name: Optional user name; used as the session file owner.
            sys_code: Optional system code.

        Returns:
            TaskResponse: The created task.

        Raises:
            ValueError: If cron, resource or file freeze validation fails.
            RuntimeError: If scheduler.add_job fails (DB is rolled back).
        """
        # 1. Validate cron expression (fail-fast before any DB write)
        _validate_cron(request.cron_expression)

        # 2. Validate referenced resources
        if self._resource_validator is not None:
            self._resource_validator(request.payload)

        # 3. Generate task_id (before the file freeze: copies target the
        #    task scope keyed by this id)
        task_id = str(uuid.uuid4())

        # 4. Freeze payload files into the task scope; persist only
        #    task-scoped IDs (never session IDs, never file_path)
        owner_id = (user_name or "").strip()
        payload_data = request.payload.model_dump()
        ext_info, copied_files = self._freeze_payload_files(
            request.payload, owner_id=owner_id, task_id=task_id
        )
        payload_data["ext_info"] = ext_info

        # 5. Write DB row (compensate frozen files on failure)
        entity_dict = {
            "task_id": task_id,
            "task_name": request.task_name,
            "description": request.description,
            "task_type": "chat_replay",
            "cron_expression": request.cron_expression,
            "payload_json": ChatReplayPayload(**payload_data).model_dump_json(),
            "enabled": True,
            "user_name": user_name,
            "sys_code": sys_code,
        }
        try:
            created = self._task_dao.create(entity_dict)
        except Exception:
            logger.exception("DB create failed for task %s", task_id)
            if copied_files:
                self._delete_task_files_quietly(owner_id, task_id)
            raise

        # 6. Add scheduler job (rollback DB + frozen files on failure)
        if self._scheduler is not None:
            try:
                await self._scheduler.add_job(
                    job_id=task_id,
                    cron_expression=request.cron_expression,
                    func=self._runner,
                    kwargs={"task_id": task_id},
                )
            except Exception:
                logger.exception("add_job failed, rolling back DB for task %s", task_id)
                self._task_dao.delete({"task_id": task_id})
                if copied_files:
                    self._delete_task_files_quietly(owner_id, task_id)
                raise

        # 7. Return TaskResponse
        return self._to_task_response(created)

    async def list_tasks(self, enabled_only: bool = False) -> List[TaskResponse]:
        """List all tasks, optionally filtering by enabled status.

        Merges ``next_run_time`` from the scheduler for each task so that
        the list API returns the same field as the detail API.

        Args:
            enabled_only: If True, only return enabled tasks.

        Returns:
            List[TaskResponse]: The list of tasks.
        """
        if enabled_only:
            rows = self._task_dao.list_enabled()
        else:
            rows = self._task_dao.get_list({})

        # Batch-lookup next_run_time from scheduler
        next_run_map: dict = {}
        if self._scheduler is not None:
            for job_info in self._scheduler.list_jobs():
                jid = job_info.get("job_id")
                nrt = job_info.get("next_run_time")
                if jid is not None:
                    next_run_map[jid] = nrt

        return [
            self._to_task_response(row, next_run_time=next_run_map.get(row["task_id"]))
            for row in rows
        ]

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Get a single task by ID, including next_run_time from scheduler.

        Args:
            task_id: The task UUID.

        Returns:
            Optional[TaskResponse]: The task, or None if not found.
        """
        row = self._task_dao.get_one({"task_id": task_id})
        if row is None:
            return None

        # Merge next_run_time from scheduler
        next_run_time = None
        if self._scheduler is not None:
            job_info = self._scheduler.get_job(task_id)
            if job_info is not None and isinstance(job_info, dict):
                next_run_time = job_info.get("next_run_time")

        return self._to_task_response(row, next_run_time=next_run_time)

    async def update_task(
        self, task_id: str, request: UpdateTaskRequest
    ) -> TaskResponse:
        """Update task fields. If cron changes, reschedule the job.

        Consistency strategy (scheduler-first for cron changes):
            1. Validate new cron expression (fail-fast)
            2. If cron changed, reschedule scheduler job BEFORE DB write
               - remove old job (best-effort, may be missing after restart)
               - add new job; if this fails, attempt to restore old job + raise
            3. Write DB only after scheduler succeeds

        Non-cron fields (task_name, description) are updated directly in DB
        without touching the scheduler.

        Args:
            task_id: The task UUID.
            request: The update request (partial fields).

        Returns:
            TaskResponse: The updated task.

        Raises:
            ValueError: If the new cron expression is invalid or task not found.
            RuntimeError: If scheduler.add_job fails (DB is NOT changed).
        """
        update_dict = {}
        if request.task_name is not None:
            update_dict["task_name"] = request.task_name
        if request.description is not None:
            update_dict["description"] = request.description

        # Payload-level merge: only user_input / model_name are user-editable
        # post-creation. Read the frozen payload_json, overwrite just those two
        # fields, then re-validate + re-serialise so every other payload field
        # (skill_id / connector_ids / chat_mode / ext_info / ...) is preserved.
        # This does NOT touch the scheduler (only cron changes reschedule).
        payload_changed = (
            request.user_input is not None or request.model_name is not None
        )
        if payload_changed:
            payload_row = self._task_dao.get_one({"task_id": task_id})
            if payload_row is None:
                raise ValueError(f"Task not found: {task_id}")
            payload_json = payload_row.get("payload_json")
            payload_data = json.loads(payload_json) if payload_json else {}
            if request.user_input is not None:
                payload_data["user_input"] = request.user_input
            if request.model_name is not None:
                payload_data["model_name"] = request.model_name
            update_dict["payload_json"] = ChatReplayPayload(
                **payload_data
            ).model_dump_json()

        cron_changed = request.cron_expression is not None
        if cron_changed:
            _validate_cron(request.cron_expression)
            update_dict["cron_expression"] = request.cron_expression

        # If cron changed, reschedule scheduler job BEFORE DB write
        if cron_changed and self._scheduler is not None:
            # Read old cron so we can attempt rollback on failure
            old_row = self._task_dao.get_one({"task_id": task_id})
            old_cron = old_row["cron_expression"] if old_row else None

            # Remove old job (best-effort: may already be gone after restart)
            try:
                await self._scheduler.remove_job(task_id)
            except ValueError:
                logger.warning(
                    "Scheduler job %s not found during update remove; "
                    "will add new job directly",
                    task_id,
                )

            # Add new job; on failure, attempt to restore old schedule
            try:
                await self._scheduler.add_job(
                    job_id=task_id,
                    cron_expression=request.cron_expression,
                    func=self._runner,
                    kwargs={"task_id": task_id},
                )
            except Exception:
                logger.exception(
                    "add_job failed for task %s with new cron %s; "
                    "attempting to restore old schedule",
                    task_id,
                    request.cron_expression,
                )
                # Best-effort restore old schedule
                if old_cron is not None:
                    try:
                        await self._scheduler.add_job(
                            job_id=task_id,
                            cron_expression=old_cron,
                            func=self._runner,
                            kwargs={"task_id": task_id},
                        )
                    except Exception:
                        logger.exception(
                            "Failed to restore old schedule for task %s",
                            task_id,
                        )
                raise

        # Update DB (only reached if scheduler succeeded or no cron change)
        updated = self._task_dao.update({"task_id": task_id}, update_dict)

        return self._to_task_response(updated)

    async def toggle_task(self, task_id: str, enabled: bool) -> TaskResponse:
        """Enable or disable a task (pause/resume scheduler job).

        DB enabled flag is always updated. If the scheduler job is missing
        (e.g. after restart with MemoryJobStore), the ValueError is caught
        and logged so the DB state still reflects the user's intent.

        Args:
            task_id: The task UUID.
            enabled: True to enable (resume), False to disable (pause).

        Returns:
            TaskResponse: The updated task.
        """
        updated = self._task_dao.update({"task_id": task_id}, {"enabled": enabled})

        if self._scheduler is not None:
            try:
                if enabled:
                    self._scheduler.resume_job(task_id)
                else:
                    self._scheduler.pause_job(task_id)
            except ValueError:
                logger.warning(
                    "Scheduler job %s not found during toggle (enabled=%s); "
                    "DB updated, scheduler skipped",
                    task_id,
                    enabled,
                )

        return self._to_task_response(updated)

    async def delete_task(self, task_id: str) -> None:
        """Delete a task: best-effort remove scheduler job, then delete DB row.

        If the scheduler job is already gone (e.g. after a restart with
        MemoryJobStore), the ValueError is caught and logged so the DB
        row can still be cleaned up. After the DB row is removed, files
        frozen into the task scope at creation time are also deleted
        best-effort so they do not linger as unreachable orphans.

        Args:
            task_id: The task UUID.
        """
        # Read owner_id BEFORE deleting the row (mirror the normalization used
        # when freezing files: ``(user_name or "").strip()`` in create_task).
        # The DB stores the raw user_name; the session_file registry matches
        # owner_id exactly, so it must be stripped or the files won't be found.
        existing = self._task_dao.get_one({"task_id": task_id})
        owner_id = (existing.get("user_name") or "").strip() if existing else ""

        # Best-effort remove scheduler job
        if self._scheduler is not None:
            try:
                await self._scheduler.remove_job(task_id)
            except ValueError:
                logger.warning(
                    "Scheduler job %s not found during delete; "
                    "proceeding with DB cleanup",
                    task_id,
                )

        # Delete DB row
        self._task_dao.delete({"task_id": task_id})

        # Best-effort clean up task-scope frozen files created at task
        # creation; skip when there is no owner (pure-text tasks never freeze
        # files). Storage failures must not block the deletion.
        if owner_id:
            self._delete_task_files_quietly(owner_id, task_id)

    async def list_runs(
        self, task_id: str, limit: int = 50, offset: int = 0
    ) -> List[RunResponse]:
        """List execution runs for a task, newest first.

        Args:
            task_id: The task UUID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List[RunResponse]: The run records, newest first.
        """
        rows = self._run_dao.list_by_task_id(task_id, limit=limit, offset=offset)
        return [self._to_run_response(row) for row in rows]

    async def get_run(self, task_id: str, run_id: str) -> Optional[RunResponse]:
        """Get a single run record.

        Args:
            task_id: The task UUID (for ownership verification).
            run_id: The run UUID.

        Returns:
            Optional[RunResponse]: The run record, or None if not found
                or task_id mismatch.
        """
        row = self._run_dao.get_one({"run_id": run_id})
        if row is None:
            return None
        # Verify task_id ownership
        if row.get("task_id") != task_id:
            return None
        return self._to_run_response(row)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _freeze_payload_files(
        self, payload: ChatReplayPayload, *, owner_id: str, task_id: str
    ) -> Tuple[Dict[str, Any], bool]:
        """Copy ``ext_info.file_ids`` into the task scope for persistence.

        Returns the ``ext_info`` dict to persist (with task-scoped IDs) and
        whether any files were copied (so later failures can be compensated).
        Legacy ``file_path`` / pure-text payloads are returned untouched.

        Raises:
            ValueError: On malformed file input, missing owner/session, an
                unavailable registry, or a rejected copy (foreign or
                wrong-session IDs surface one indistinguishable message).
        """
        ext_info = dict(payload.ext_info or {})
        spec = parse_file_input(ext_info)
        if not spec.file_ids:
            return ext_info, False
        if not owner_id:
            raise ValueError(
                "an authenticated owner is required to freeze session files"
            )
        if self._session_file_registry is None:
            raise ValueError("session file storage is unavailable")
        session_id = (
            ext_info.get("session_id")
            or ext_info.get("conversation_uid")
            or ext_info.get("conv_uid")
        )
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("ext_info.session_id is required to freeze session files")
        try:
            records = self._session_file_registry.copy_session_to_task(
                owner_id=owner_id,
                session_id=session_id.strip(),
                file_ids=list(spec.file_ids),
                task_id=task_id,
            )
        except Exception as error:
            # Single indistinguishable message: foreign and wrong-session
            # rejections never leak which files exist.
            message = getattr(error, "message", None) or (
                "could not freeze session files for the task"
            )
            raise ValueError(message) from error
        ext_info["file_ids"] = [record.file_id for record in records]
        ext_info.pop("file_path", None)
        return ext_info, True

    def _delete_task_files_quietly(self, owner_id: str, task_id: str) -> None:
        """Best-effort compensating delete of files frozen into a task scope."""
        if self._session_file_registry is None:
            return
        try:
            task_files = self._session_file_registry.list_task_files(
                owner_id=owner_id, task_id=task_id
            )
            for record in task_files:
                self._session_file_registry.delete_task_file(
                    owner_id=owner_id, task_id=task_id, file_id=record.file_id
                )
        except Exception:
            logger.exception("Failed to compensate frozen files for task %s", task_id)

    def _to_task_response(
        self,
        task_dict: dict,
        next_run_time: Optional[str] = None,
    ) -> TaskResponse:
        """Convert a DAO task dict to a TaskResponse.

        Args:
            task_dict: The dict from ScheduledTaskDao.to_response().
            next_run_time: Optional next run time from scheduler.

        Returns:
            TaskResponse: The response object.
        """
        # Parse payload_json back to ChatReplayPayload
        payload = None
        payload_json = task_dict.get("payload_json")
        if payload_json:
            try:
                payload_data = json.loads(payload_json)
                payload = ChatReplayPayload(**payload_data)
            except (json.JSONDecodeError, Exception):
                logger.warning(
                    "Failed to parse payload_json for task %s",
                    task_dict.get("task_id"),
                )

        return TaskResponse(
            task_id=task_dict["task_id"],
            task_name=task_dict["task_name"],
            description=task_dict.get("description"),
            task_type=task_dict.get("task_type", "chat_replay"),
            cron_expression=task_dict["cron_expression"],
            payload=payload,
            enabled=task_dict.get("enabled", True),
            created_at=task_dict.get("created_at"),
            updated_at=task_dict.get("updated_at"),
            user_name=task_dict.get("user_name"),
            sys_code=task_dict.get("sys_code"),
            next_run_time=next_run_time,
        )

    def _to_run_response(self, run_dict: dict) -> RunResponse:
        """Convert a DAO run dict to a RunResponse.

        Args:
            run_dict: The dict from ScheduledRunDao.to_response().

        Returns:
            RunResponse: The response object.
        """
        # started_at / finished_at are datetime objects from DAO,
        # convert to ISO 8601 str for the response schema
        started_at = run_dict.get("started_at")
        if started_at is not None and not isinstance(started_at, str):
            started_at = started_at.isoformat()

        finished_at = run_dict.get("finished_at")
        if finished_at is not None and not isinstance(finished_at, str):
            finished_at = finished_at.isoformat()

        return RunResponse(
            run_id=run_dict["run_id"],
            task_id=run_dict["task_id"],
            started_at=started_at,
            finished_at=finished_at,
            status=run_dict["status"],
            result_summary=run_dict.get("result_summary"),
            error_message=run_dict.get("error_message"),
            output_conv_uid=run_dict.get("output_conv_uid"),
        )
