"""REST API for the semantic center (S7).

Thin wrappers over :class:`SemanticService` / :class:`SemanticSyncService`,
returning the repo-standard ``Result`` envelope. Registered by
``dbgpt_server`` under the ``/api`` prefix, so paths below surface as
``/api/v1/semantic/*``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from dbgpt_serve.core import Result
from dbgpt_serve.semantic.service import SemanticService
from dbgpt_serve.semantic.sync import SemanticSyncService

logger = logging.getLogger(__name__)

router = APIRouter()

_service: Optional[SemanticService] = None


def get_semantic_service() -> SemanticService:
    """Process-wide service singleton (daos are lightweight)."""
    global _service
    if _service is None:
        _service = SemanticService()
    return _service


def _connector(db_name: str) -> Any:
    from dbgpt._private.config import Config
    from dbgpt_serve.datasource.manages import ConnectorManager

    manager = ConnectorManager.get_instance(Config().SYSTEM_APP)
    return manager.get_connector(db_name)


# ---- spaces ----
@router.get("/v1/semantic/spaces")
async def list_spaces():
    return Result.succ(get_semantic_service().list_spaces())


@router.get("/v1/semantic/spaces/{ds_id}")
async def get_space(ds_id: int):
    space = get_semantic_service().get_space(ds_id)
    if not space:
        raise HTTPException(status_code=404, detail=f"space {ds_id} not found")
    return Result.succ(space)


@router.post("/v1/semantic/spaces/{ds_id}/activate")
async def activate_space(ds_id: int, payload: Dict[str, Any] = Body(default={})):
    service = get_semantic_service()
    try:
        return Result.succ(
            service.activate(
                ds_id,
                sampling_limit=int(payload.get("sampling_limit", 42)),
                run_draft_generation=bool(payload.get("run_draft_generation", False)),
                embedding_model=str(payload.get("embedding_model", "bge-large-zh")),
                user=payload.get("user"),
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/v1/semantic/spaces/{ds_id}/sync")
async def sync_space(ds_id: int, payload: Dict[str, Any] = Body(default={})):
    space = get_semantic_service().get_space(ds_id)
    if not space:
        raise HTTPException(status_code=404, detail=f"space {ds_id} not found")
    db_name = str(payload.get("db_name") or space["conn_id"])
    try:
        connector = _connector(db_name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"connector unavailable: {e}")
    report = SemanticSyncService().sync(db_name, connector)
    return Result.succ(asdict(report))


@router.get("/v1/semantic/spaces/{ds_id}/coverage")
async def coverage(ds_id: int):
    return Result.succ(get_semantic_service().coverage(ds_id))


# ---- L1 catalog ----
@router.get("/v1/semantic/spaces/{ds_id}/tables")
async def list_tables(ds_id: int, status: str = Query(default="active")):
    return Result.succ(get_semantic_service().list_tables(ds_id, status=status))


@router.get("/v1/semantic/tables/{table_id}/columns")
async def list_columns(table_id: int, ds_id: int = Query(...)):
    return Result.succ(get_semantic_service().list_columns(ds_id, table_id))


# ---- L2 entries ----
@router.get("/v1/semantic/spaces/{ds_id}/entries")
async def list_entries(ds_id: int, status: Optional[str] = Query(default=None)):
    return Result.succ(get_semantic_service().list_entries(ds_id, status=status))


@router.post("/v1/semantic/spaces/{ds_id}/entries")
async def create_entry(ds_id: int, payload: Dict[str, Any] = Body(...)):
    return Result.succ(
        get_semantic_service().create_entry(
            ds_id,
            payload,
            user=payload.get("user"),
            provenance=payload.get("provenance", "manual"),
        )
    )


@router.post("/v1/semantic/entries/{entry_id}/review")
async def review_entry(entry_id: int, payload: Dict[str, Any] = Body(...)):
    service = get_semantic_service()
    try:
        return Result.succ(
            service.review_entry(
                entry_id,
                str(payload.get("action", "")),
                user=payload.get("user"),
                updates=payload.get("updates"),
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- L3 metrics ----
@router.get("/v1/semantic/spaces/{ds_id}/metrics")
async def list_metrics(ds_id: int, status: Optional[str] = Query(default=None)):
    return Result.succ(get_semantic_service().list_metrics(ds_id, status=status))


@router.post("/v1/semantic/spaces/{ds_id}/metrics")
async def create_metric(ds_id: int, payload: Dict[str, Any] = Body(...)):
    metric = get_semantic_service().create_metric(
        ds_id,
        payload,
        user=payload.get("user"),
        provenance=payload.get("provenance", "manual"),
        suite_id=payload.get("suite_id"),
    )
    return Result.succ({"id": metric.id, "metric_name": metric.metric_name})


@router.post("/v1/semantic/metrics/{metric_id}/publish")
async def publish_metric(metric_id: int, payload: Dict[str, Any] = Body(default={})):
    service = get_semantic_service()
    try:
        return Result.succ(
            service.publish_metric(
                metric_id,
                user=payload.get("user"),
                change_note=str(payload.get("change_note", "")),
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- L4/L5/L6 ----
@router.get("/v1/semantic/spaces/{ds_id}/relations")
async def list_relations(ds_id: int):
    return Result.succ(get_semantic_service().list_relations(ds_id))


@router.get("/v1/semantic/spaces/{ds_id}/examples")
async def list_examples(ds_id: int, status: Optional[str] = Query(default=None)):
    return Result.succ(get_semantic_service().list_examples(ds_id, status=status))


@router.get("/v1/semantic/spaces/{ds_id}/rules")
async def list_rules(ds_id: int, status: Optional[str] = Query(default=None)):
    return Result.succ(get_semantic_service().list_rules(ds_id, status=status))


@router.post("/v1/semantic/rules/{rule_id}/status")
async def set_rule_status(rule_id: int, payload: Dict[str, Any] = Body(...)):
    service = get_semantic_service()
    try:
        return Result.succ(
            service.set_rule_status(rule_id, str(payload.get("status", "active")))
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
