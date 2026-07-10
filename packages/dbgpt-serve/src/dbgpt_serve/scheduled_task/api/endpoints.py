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


# ── 1. POST / — 创建定时任务 ────────────────────────────────────────


@router.post("/", response_model=Result)
async def create_task(
    request: CreateTaskRequest,
    user_token: UserRequest = Depends(get_user_from_headers),
    service: ScheduledTaskService = Depends(get_service),
):
    """Create a new scheduled task."""
    try:
        # Prefer the display name supplied by the client; fall back to the
        # authenticated user's nick name / real name / id.
        user_name = request.creator_name or (
            (user_token.nick_name or user_token.real_name or user_token.user_id)
            if user_token
            else None
        )
        resp = await service.create_task(request, user_name=user_name)
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
    service: ScheduledTaskService = Depends(get_service),
):
    """List all scheduled tasks."""
    try:
        tasks = await service.list_tasks(enabled_only=enabled_only)
        return Result.succ(tasks)
    except Exception as e:
        logger.exception("List scheduled tasks failed")
        return Result.failed(msg=str(e))


# ── 3. GET /{task_id} — 任务详情 ───────────────────────────────────


@router.get("/{task_id}", response_model=Result)
async def get_task(
    task_id: str,
    service: ScheduledTaskService = Depends(get_service),
):
    """Get a single scheduled task by ID."""
    resp = await service.get_task(task_id)
    if resp is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return Result.succ(resp)


# ── 4. PUT /{task_id} — 更新任务 ───────────────────────────────────


@router.put("/{task_id}", response_model=Result)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    service: ScheduledTaskService = Depends(get_service),
):
    """Update an existing scheduled task."""
    try:
        resp = await service.update_task(task_id, request)
        return Result.succ(resp)
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
    service: ScheduledTaskService = Depends(get_service),
):
    """Enable or disable a scheduled task."""
    try:
        resp = await service.toggle_task(task_id, body.enabled)
        return Result.succ(resp)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Toggle scheduled task failed")
        return Result.failed(msg=str(e))


# ── 6. DELETE /{task_id} — 删除任务 ────────────────────────────────


@router.delete("/{task_id}", response_model=Result)
async def delete_task(
    task_id: str,
    service: ScheduledTaskService = Depends(get_service),
):
    """Delete a scheduled task and its scheduler job."""
    try:
        await service.delete_task(task_id)
        return Result.succ(None)
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
    service: ScheduledTaskService = Depends(get_service),
):
    """List execution runs for a scheduled task."""
    try:
        runs = await service.list_runs(task_id, limit=limit, offset=offset)
        return Result.succ(runs)
    except Exception as e:
        logger.exception("List runs failed")
        return Result.failed(msg=str(e))


# ── 8. GET /{task_id}/runs/{run_id} — 单次执行详情 ────────────────


@router.get("/{task_id}/runs/{run_id}", response_model=Result)
async def get_run(
    task_id: str,
    run_id: str,
    service: ScheduledTaskService = Depends(get_service),
):
    """Get details of a single execution run."""
    resp = await service.get_run(task_id, run_id)
    if resp is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return Result.succ(resp)
