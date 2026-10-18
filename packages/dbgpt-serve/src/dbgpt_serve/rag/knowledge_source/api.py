"""Knowledge source API endpoints.

Mounted on the RagServe router with the shape
``/spaces/{space_id}/knowledge_sources/...`` (same prefix as the wiki
endpoints). Contract:

- GET  /knowledge_sources/types          — connector metas (dynamic forms)
- POST /spaces/{id}/knowledge_sources    — create + validate + encrypt
- GET/PUT/DELETE /spaces/{id}/knowledge_sources[/{sid}]
- GET  /spaces/{id}/knowledge_sources/{sid}/resources?parent_id
- POST /spaces/{id}/knowledge_sources/{sid}/{sync|pause|resume}
- GET  /spaces/{id}/knowledge_sources/{sid}/logs
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

router = APIRouter()
global_system_app: Optional[SystemApp] = None


def _service():
    from dbgpt_serve.rag.knowledge_source.service import get_knowledge_source_service

    if global_system_app is None:
        raise HTTPException(
            status_code=503, detail="knowledge source service not started"
        )
    return get_knowledge_source_service(global_system_app)


# ---------------------------------------------------------------- schemas
class KsCreateRequest(BaseModel):
    name: Optional[str] = None
    type: str = Field(..., min_length=1)
    config: Dict[str, str] = Field(
        default_factory=dict,
        description="plaintext credentials; encrypted at rest",
    )
    target_resource_ids: List[str] = Field(default_factory=list)
    interval_minutes: int = 0
    sync_mode: str = "incremental"
    conflict_strategy: str = "overwrite"
    sync_deletions: bool = False


class KsUpdateRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, str]] = None
    target_resource_ids: Optional[List[str]] = None
    interval_minutes: Optional[int] = None
    sync_mode: Optional[str] = None
    conflict_strategy: Optional[str] = None
    sync_deletions: Optional[bool] = None


# ---------------------------------------------------------------- endpoints
@router.get("/knowledge_sources/types")
async def ks_types() -> Result:
    return Result.succ(_service().list_connector_metas())


@router.post("/spaces/{space_id}/knowledge_sources")
async def ks_create(space_id: int, request: KsCreateRequest) -> Result:
    _space_or_404(space_id)
    service = _service()
    row = await service.create(
        space_id=space_id,
        name=request.name,
        type=request.type,
        plain_config=request.config,
        target_resource_ids=request.target_resource_ids,
        interval_minutes=request.interval_minutes,
        sync_mode=request.sync_mode,
        conflict_strategy=request.conflict_strategy,
        sync_deletions=request.sync_deletions,
    )
    return Result.succ(row)


@router.get("/spaces/{space_id}/knowledge_sources")
async def ks_list(space_id: int) -> Result:
    return Result.succ(_service().list_by_space(space_id))


def _space_or_404(space_id: int):
    from ..models.models import KnowledgeSpaceDao

    spaces = KnowledgeSpaceDao().get_knowledge_space_by_ids([space_id])
    if not spaces:
        raise HTTPException(status_code=404, detail=f"space {space_id} not found")
    return spaces[0]


def _source_or_404(space_id: int, source_id: int):
    source = _service().get(source_id)
    if source is None or source["space_id"] != space_id:
        raise HTTPException(
            status_code=404,
            detail=f"knowledge source {source_id} not found",
        )
    return source


@router.get("/spaces/{space_id}/knowledge_sources/{source_id}")
async def ks_get(space_id: int, source_id: int) -> Result:
    return Result.succ(_source_or_404(space_id, source_id))


@router.put("/spaces/{space_id}/knowledge_sources/{source_id}")
async def ks_update(space_id: int, source_id: int, request: KsUpdateRequest) -> Result:
    _source_or_404(space_id, source_id)
    updates: Dict[str, Any] = {}
    for field in (
        "name",
        "interval_minutes",
        "sync_mode",
        "conflict_strategy",
        "sync_deletions",
    ):
        value = getattr(request, field)
        if value is not None:
            updates[field] = value
    if request.config is not None:
        updates["plain_config"] = request.config  # re-encrypted in service.update
    if request.target_resource_ids is not None:
        updates["target_resource_ids"] = request.target_resource_ids
    import json

    body = dict(updates)
    if "target_resource_ids" in body:
        body["target_resource_ids"] = json.dumps(body["target_resource_ids"])
    _service().update(source_id, body)
    return Result.succ(True)


@router.delete("/spaces/{space_id}/knowledge_sources/{source_id}")
async def ks_delete(space_id: int, source_id: int) -> Result:
    _source_or_404(space_id, source_id)
    return Result.succ(_service().delete(source_id))


@router.get("/spaces/{space_id}/knowledge_sources/{source_id}/resources")
async def ks_resources(space_id: int, source_id: int, parent_id: str = "") -> Result:
    _source_or_404(space_id, source_id)
    return Result.succ(await _service().list_resources(source_id, parent_id))


@router.post("/spaces/{space_id}/knowledge_sources/{source_id}/sync")
async def ks_sync(space_id: int, source_id: int) -> Result:
    _source_or_404(space_id, source_id)
    summary = await _service().run_sync(source_id, trigger="manual")
    return Result.succ(summary)


@router.post("/spaces/{space_id}/knowledge_sources/{source_id}/pause")
async def ks_pause(space_id: int, source_id: int) -> Result:
    _source_or_404(space_id, source_id)
    _service().update(source_id, {"status": "paused"})
    return Result.succ(True)


@router.post("/spaces/{space_id}/knowledge_sources/{source_id}/resume")
async def ks_resume(space_id: int, source_id: int) -> Result:
    _source_or_404(space_id, source_id)
    _service().update(source_id, {"status": "active"})
    return Result.succ(True)


@router.get("/spaces/{space_id}/knowledge_sources/{source_id}/logs")
async def ks_logs(space_id: int, source_id: int) -> Result:
    _source_or_404(space_id, source_id)
    return Result.succ(_service().list_logs(source_id))


def init_knowledge_source_endpoints(system_app: SystemApp, config: Any) -> None:
    global global_system_app
    global_system_app = system_app
