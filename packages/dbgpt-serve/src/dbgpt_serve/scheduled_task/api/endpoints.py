"""REST API endpoints for scheduled task management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

from ..service.service import ScheduledTaskService
from .schemas import (
    CreateTaskRequest,
    DashboardRefreshPayload,
    ToggleTaskRequest,
    UpdateTaskRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

global_system_app: Optional[SystemApp] = None
_service_instance: Optional[ScheduledTaskService] = None


def init_endpoints(system_app: SystemApp, service: ScheduledTaskService) -> None:
    """Initialise module-level state.

    Called by ``ScheduledTaskServe.init_app`` after the service instance is
    ready.  The *service* is passed directly (unlike the connector module
    which registers via ``SystemApp``) because ``ScheduledTaskService`` is
    **not** a ``BaseComponent`` — it is a plain class that needs a scheduler
    and runner injected by the Serve layer.

    Args:
        system_app: The global SystemApp instance.
        service: A fully-initialised ScheduledTaskService.
    """
    global global_system_app, _service_instance
    global_system_app = system_app
    _service_instance = service


def get_service() -> ScheduledTaskService:
    """FastAPI dependency — returns the singleton service instance."""
    if _service_instance is None:
        raise HTTPException(
            status_code=503, detail="Scheduled task service not initialized"
        )
    return _service_instance


def _owner_id(user: UserRequest) -> str:
    actor_id = user.user_id or user.user_name
    if not actor_id:
        raise HTTPException(status_code=401, detail="Authenticated user id is required")
    return actor_id


def _check_dashboard_access(task, user: UserRequest) -> None:
    """The unified task UI must retain dashboard-scoped schedule permissions."""
    from dbgpt_app.openapi.api_v1.dashboard.api import _user_id, get_dashboard_service
    from dbgpt_app.openapi.api_v1.dashboard.models import (
        DashboardAccessDeniedError,
        DashboardNotFoundError,
    )
    from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardAction

    if not isinstance(task.payload, DashboardRefreshPayload):
        raise HTTPException(status_code=404, detail="Dashboard schedule not found")
    # Apply the same identity provider as the resource API, including its
    # production-mode rejection of the development fallback identity.
    actor_id = _user_id(user)
    if task.owner_id and task.owner_id != actor_id:
        raise HTTPException(status_code=404, detail="Dashboard schedule not found")
    try:
        get_dashboard_service().require_permission(
            task.payload.dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc
    except DashboardAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail="Schedule access denied") from exc


async def _get_owned_task_or_404(
    service: ScheduledTaskService,
    task_id: str,
    owner_id: str,
    user: UserRequest,
):
    """Check task ownership and, for dashboards, current resource permissions."""

    task = await service.get_task(task_id, owner_id=owner_id)
    if task is None or task.task_type not in {"chat_replay", "dashboard_refresh"}:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task.task_type == "dashboard_refresh":
        _check_dashboard_access(task, user)
    return task


# ── 1. POST / — 创建定时任务 ────────────────────────────────────────


@router.post("/", response_model=Result)
async def create_task(
    request: CreateTaskRequest,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Create a new scheduled task."""
    try:
        if request.task_type != "chat_replay":
            raise ValueError(
                "Dashboard refresh schedules must be created from the dashboard API."
            )
        # Prefer the display name supplied by the client; fall back to the
        # authenticated user's nick name / real name / id.
        owner_id = _owner_id(user_token)
        user_name = request.creator_name or (
            (user_token.nick_name or user_token.real_name or user_token.user_id)
            if user_token
            else None
        )
        resource_type = None
        resource_id = None
        ext_info = dict(request.payload.ext_info or {})
        dataset_id = ext_info.get("dataset_id")
        if isinstance(dataset_id, str) and dataset_id:
            # Lazy import avoids a dbgpt-serve -> dbgpt-app import cycle during
            # module initialization.  Creation must prove ownership before the
            # scheduler stores a replayable resource binding.
            from dbgpt_app.openapi.api_v1.uploaded_dataset_registry import (
                UploadedDatasetService,
            )

            UploadedDatasetService().resolve_owned(dataset_id, owner_id)
            for unsafe_key in (
                "file_path",
                "file_paths",
                "database_name",
                "database_path",
            ):
                ext_info.pop(unsafe_key, None)
            ext_info["dataset_id"] = dataset_id
            request.payload.ext_info = ext_info
            resource_type = "uploaded_dataset"
            resource_id = dataset_id
        elif ext_info.get("file_path") or ext_info.get("file_paths"):
            from dbgpt_app.openapi.api_v1.agentic_data_api import (
                _parse_uploaded_file_paths,
            )
            from dbgpt_app.openapi.api_v1.uploaded_dataset_registry import (
                validate_legacy_user_paths,
            )

            validate_legacy_user_paths(_parse_uploaded_file_paths(ext_info), owner_id)
        resp = await service.create_task(
            request,
            user_name=user_name,
            owner_id=owner_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        return Result.succ(resp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Create scheduled task failed")
        return Result.failed(msg=str(e))


# ── 2. GET / — 任务列表 ────────────────────────────────────────────


@router.get("/", response_model=Result)
async def list_tasks(
    enabled_only: bool = Query(False, description="Only return enabled tasks"),
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """List all scheduled tasks."""
    try:
        tasks = await service.list_tasks(
            enabled_only=enabled_only,
            owner_id=_owner_id(user_token),
        )
        visible_tasks = []
        for task in tasks:
            if task.task_type == "dashboard_refresh":
                try:
                    _check_dashboard_access(task, user_token)
                except HTTPException as exc:
                    if exc.status_code in (401, 403, 404):
                        continue
                    raise
            elif task.task_type != "chat_replay":
                continue
            visible_tasks.append(task)
        return Result.succ(visible_tasks)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("List scheduled tasks failed")
        return Result.failed(msg=str(e))


# ── 3. GET /{task_id} — 任务详情 ───────────────────────────────────


@router.get("/{task_id}", response_model=Result)
async def get_task(
    task_id: str,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Get a single scheduled task by ID."""
    resp = await _get_owned_task_or_404(
        service, task_id, _owner_id(user_token), user_token
    )
    return Result.succ(resp)


# ── 4. PUT /{task_id} — 更新任务 ───────────────────────────────────


@router.put("/{task_id}", response_model=Result)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Update an existing scheduled task."""
    try:
        owner_id = _owner_id(user_token)
        task = await _get_owned_task_or_404(service, task_id, owner_id, user_token)
        if task.task_type == "dashboard_refresh":
            # Delegate mutations to the existing resource API so RBAC, input
            # validation and the dashboard audit trail remain identical.
            from dbgpt_app.openapi.api_v1.dashboard import api as dashboard_api

            return await dashboard_api.update_dashboard_schedule(
                task.payload.dashboard_id,
                task_id,
                dashboard_api.DashboardScheduleUpdateRequest(
                    **request.model_dump(exclude_unset=True)
                ),
                user_token,
                dashboard_api.get_dashboard_service(),
                service,
            )
        resp = await service.update_task(task_id, request, owner_id=owner_id)
        return Result.succ(resp)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Update scheduled task failed")
        return Result.failed(msg=str(e))


# ── 5. POST /{task_id}/toggle — 启停任务 ──────────────────────────


@router.post("/{task_id}/toggle", response_model=Result)
async def toggle_task(
    task_id: str,
    body: ToggleTaskRequest,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Enable or disable a scheduled task."""
    try:
        owner_id = _owner_id(user_token)
        task = await _get_owned_task_or_404(service, task_id, owner_id, user_token)
        if task.task_type == "dashboard_refresh":
            from dbgpt_app.openapi.api_v1.dashboard import api as dashboard_api

            return await dashboard_api.toggle_dashboard_schedule(
                task.payload.dashboard_id,
                task_id,
                dashboard_api.DashboardScheduleToggleRequest(enabled=body.enabled),
                user_token,
                dashboard_api.get_dashboard_service(),
                service,
            )
        resp = await service.toggle_task(task_id, body.enabled, owner_id=owner_id)
        return Result.succ(resp)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Toggle scheduled task failed")
        return Result.failed(msg=str(e))


# ── 6. DELETE /{task_id} — 删除任务 ────────────────────────────────


@router.delete("/{task_id}", response_model=Result)
async def delete_task(
    task_id: str,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Delete a scheduled task and its scheduler job."""
    try:
        owner_id = _owner_id(user_token)
        task = await _get_owned_task_or_404(service, task_id, owner_id, user_token)
        if task.task_type == "dashboard_refresh":
            from dbgpt_app.openapi.api_v1.dashboard import api as dashboard_api

            return await dashboard_api.delete_dashboard_schedule(
                task.payload.dashboard_id,
                task_id,
                user_token,
                dashboard_api.get_dashboard_service(),
                service,
            )
        await service.delete_task(task_id, owner_id=owner_id)
        return Result.succ(None)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Delete scheduled task failed")
        return Result.failed(msg=str(e))


# ── 7. GET /{task_id}/runs — 执行历史列表 ─────────────────────────


@router.get("/{task_id}/runs", response_model=Result)
async def list_runs(
    task_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """List execution runs for a scheduled task."""
    try:
        owner_id = _owner_id(user_token)
        await _get_owned_task_or_404(service, task_id, owner_id, user_token)
        runs = await service.list_runs(
            task_id,
            limit=limit,
            offset=offset,
            owner_id=owner_id,
        )
        return Result.succ(runs)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("List runs failed")
        return Result.failed(msg=str(e))


# ── 8. GET /{task_id}/runs/{run_id} — 单次执行详情 ────────────────


@router.get("/{task_id}/runs/{run_id}", response_model=Result)
async def get_run(
    task_id: str,
    run_id: str,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Get details of a single execution run."""
    owner_id = _owner_id(user_token)
    await _get_owned_task_or_404(service, task_id, owner_id, user_token)
    resp = await service.get_run(task_id, run_id, owner_id=owner_id)
    if resp is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return Result.succ(resp)
