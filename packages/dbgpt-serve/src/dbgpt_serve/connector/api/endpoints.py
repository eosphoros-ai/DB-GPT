"""REST API endpoints for connector management."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result, blocking_func_to_async

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import (
    ConnectorCreateRequest,
    ConnectorResponse,
    ConnectorService,
    ConnectorToolsResponse,
    ConnectorUpdateRequest,
)
from .schemas import ConnectorTypeOption

logger = logging.getLogger(__name__)

router = APIRouter()

global_system_app: Optional[SystemApp] = None


def get_service() -> ConnectorService:
    return global_system_app.get_component(
        SERVE_SERVICE_COMPONENT_NAME, ConnectorService
    )


# Synthetic catalog entry for user-defined custom MCP servers.
# Kept in sync with CustomMcpForm (Task F) on the frontend.
# Note: auth_fields here include extra keys (`options`, `default`) beyond the
# `AuthField` schema in catalog.py — the frontend CustomMcpForm tolerates both shapes.
_CUSTOM_MCP_OPTION = ConnectorTypeOption(
    type="custom_mcp",
    display_name="自定义 MCP Server",
    description="接入任意 SSE / Streamable HTTP MCP Server",
    category="custom",
    is_custom=True,
    auth_fields=[
        {
            "name": "server_uri",
            "label": "Endpoint URL",
            "type": "url",
            "required": True,
        },
        {
            # Display label intentionally generic — the form switches the
            # server_uri label/placeholder based on this value.
            "name": "transport",
            "label": "传输协议",
            "type": "select",
            "options": ["sse", "streamable_http"],
            "required": True,
            "default": "sse",
        },
        {
            # Optional free-text description shown in the agent's connector
            # prompt block. Manager.list_active prefers extra_config.description
            # over catalog.description, so this is the canonical way for users
            # to label what a custom_mcp connector exposes.
            "name": "description",
            "label": "连接器描述",
            "type": "text",
            "required": False,
        },
        {
            "name": "auth_type",
            "label": "认证方式",
            "type": "select",
            "options": ["none", "bearer", "token"],
            "required": True,
        },
        {
            "name": "token",
            "label": "Token",
            "type": "password",
            "required": False,
        },
        {
            "name": "header_name",
            "label": "Token Header 名",
            "type": "text",
            "required": False,
            "default": "Authorization",
        },
    ],
)


@router.get("/types", response_model=Result[List[ConnectorTypeOption]])
async def list_connector_types() -> Result[List[Dict[str, Any]]]:
    from dbgpt.agent.resource.connector.manager import ConnectorManager as _CM

    if global_system_app is None:
        raise HTTPException(status_code=503, detail="SystemApp not initialised")
    manager = global_system_app.get_component(
        "connector_manager", _CM, default_component=None
    )
    if manager is None:
        raise HTTPException(status_code=503, detail="ConnectorManager not available")

    options: List[ConnectorTypeOption] = []
    for entry in manager.get_catalog().list():
        options.append(
            ConnectorTypeOption(
                type=entry.type,
                display_name=entry.display_name,
                description=entry.description,
                icon=entry.icon,
                category=entry.category,
                is_custom=False,
                auth_fields=[f.model_dump() for f in entry.auth.fields],
            )
        )
    options.append(_CUSTOM_MCP_OPTION)
    return Result.succ([o.model_dump() for o in options])


@router.post("/", response_model=Result[ConnectorResponse])
async def create_connector(
    request: ConnectorCreateRequest,
    service: ConnectorService = Depends(get_service),
) -> Result[ConnectorResponse]:
    try:
        return Result.succ(
            await blocking_func_to_async(
                global_system_app, service.create_connector, request
            )
        )
    except Exception as e:
        logger.exception("Create connector failed")
        return Result.failed(msg=str(e))


@router.get("/", response_model=Result[List[ConnectorResponse]])
async def list_connectors(
    user_name: Optional[str] = Query(default=None, description="Filter by user name"),
    sys_code: Optional[str] = Query(default=None, description="Filter by system code"),
    service: ConnectorService = Depends(get_service),
) -> Result[List[ConnectorResponse]]:
    try:
        return Result.succ(
            service.list_connectors(user_name=user_name, sys_code=sys_code)
        )
    except Exception as e:
        logger.exception("List connectors failed")
        return Result.failed(msg=str(e))


class ConfirmRequest(BaseModel):
    confirm_id: str
    approved: bool


# IMPORTANT: keep these fixed-path routes BEFORE any "/{connector_id}" routes,
# otherwise FastAPI matches /{connector_id} first and treats "pending-confirms" /
# "confirm" as a connector_id value.
@router.get("/pending-confirms")
async def list_pending_confirms() -> List[dict]:
    from dbgpt.agent.resource.connector.confirmation import _PENDING_CONFIRMATIONS

    return list(_PENDING_CONFIRMATIONS.values())


@router.post("/confirm")
async def confirm_action(request: ConfirmRequest) -> Dict[str, str]:
    from dbgpt.agent.resource.connector.manager import ConnectorManager as _CM

    if global_system_app is None:
        raise HTTPException(status_code=503, detail="SystemApp not initialised")
    cm = global_system_app.get_component(
        "connector_manager", _CM, default_component=None
    )
    if cm is None:
        raise HTTPException(status_code=503, detail="ConnectorManager not available")
    registry = cm.get_confirmation_registry()
    resolved = registry.resolve(request.confirm_id, request.approved)
    if not resolved:
        raise HTTPException(status_code=404, detail="confirm_id not found or expired")
    from dbgpt.agent.resource.connector.confirmation import _PENDING_CONFIRMATIONS

    _PENDING_CONFIRMATIONS.pop(request.confirm_id, None)
    return {"status": "ok"}


@router.get("/{connector_id}", response_model=Result[ConnectorResponse])
async def get_connector(
    connector_id: str,
    service: ConnectorService = Depends(get_service),
) -> Result[ConnectorResponse]:
    connector = service.get_connector(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=404, detail=f"Connector '{connector_id}' not found"
        )
    return Result.succ(connector)


@router.put("/{connector_id}", response_model=Result[ConnectorResponse])
async def update_connector(
    connector_id: str,
    request: ConnectorUpdateRequest,
    service: ConnectorService = Depends(get_service),
) -> Result[ConnectorResponse]:
    # service.update_connector is a sync method that internally drives the
    # ConnectorManager via loop.run_until_complete(...). Calling it directly
    # from this async handler runs that on the live FastAPI event loop and
    # raises "This event loop is already running" — which the service's
    # broad except then writes back as status='error'. Mirror the POST route
    # and dispatch through blocking_func_to_async so the sync work executes
    # on a worker thread with its own fresh loop.
    try:
        return Result.succ(
            await blocking_func_to_async(
                global_system_app,
                service.update_connector,
                connector_id,
                request,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Update connector failed")
        return Result.failed(msg=str(e))


@router.delete("/{connector_id}", response_model=Result[None])
async def delete_connector(
    connector_id: str,
    service: ConnectorService = Depends(get_service),
) -> Result[None]:
    try:
        service.delete_connector(connector_id)
        return Result.succ(None)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Delete connector failed")
        return Result.failed(msg=str(e))


@router.post("/{connector_id}/test", response_model=Result[Dict[str, Any]])
async def test_connector(
    connector_id: str,
    service: ConnectorService = Depends(get_service),
) -> Result[Dict[str, Any]]:
    try:
        return Result.succ(await service.test_connection(connector_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Test connector failed")
        return Result.failed(msg=str(e))


@router.get("/{connector_id}/tools", response_model=Result[ConnectorToolsResponse])
async def get_connector_tools(
    connector_id: str,
    service: ConnectorService = Depends(get_service),
) -> Result[ConnectorToolsResponse]:
    try:
        return Result.succ(service.list_tools(connector_id))
    except HTTPException:
        # Let FastAPI surface 404 directly (matches get_connector behaviour).
        raise
    except Exception as e:
        logger.exception("Get connector tools failed")
        return Result.failed(msg=str(e))


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    global global_system_app
    system_app.register(ConnectorService, config=config)
    global_system_app = system_app


def _get_task_service():
    from ..service.scheduled_task_service import ScheduledTaskService

    return ScheduledTaskService()


@router.post("/tasks/{task_id}/toggle", response_model=Result[Dict])
async def toggle_task(task_id: str, body: Dict) -> Result[Dict]:
    try:
        svc = _get_task_service()
        enabled = body.get("enabled", True)
        return Result.succ(svc.toggle_task(task_id, enabled))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Toggle task failed")
        return Result.failed(msg=str(e))


@router.get("/tasks/{task_id}", response_model=Result[Dict])
async def get_task(task_id: str) -> Result[Dict]:
    svc = _get_task_service()
    task = svc.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return Result.succ(task)


@router.put("/tasks/{task_id}", response_model=Result[Dict])
async def update_task(task_id: str, request: Dict) -> Result[Dict]:
    try:
        svc = _get_task_service()
        return Result.succ(svc.update_task(task_id, request))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Update task failed")
        return Result.failed(msg=str(e))


@router.delete("/tasks/{task_id}", response_model=Result[None])
async def delete_task(task_id: str) -> Result[None]:
    try:
        svc = _get_task_service()
        svc.delete_task(task_id)
        return Result.succ(None)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Delete task failed")
        return Result.failed(msg=str(e))


@router.post("/{connector_id}/tasks", response_model=Result[Dict])
async def create_task(connector_id: str, request: Dict) -> Result[Dict]:
    try:
        svc = _get_task_service()
        request["connector_id"] = connector_id
        return Result.succ(svc.create_task(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Create task failed")
        return Result.failed(msg=str(e))


@router.get("/{connector_id}/tasks", response_model=Result[List[Dict]])
async def list_tasks(connector_id: str) -> Result[List[Dict]]:
    try:
        svc = _get_task_service()
        return Result.succ(svc.list_tasks(connector_id=connector_id))
    except Exception as e:
        logger.exception("List tasks failed")
        return Result.failed(msg=str(e))
