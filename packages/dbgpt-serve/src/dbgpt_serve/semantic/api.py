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


@router.post("/v1/semantic/spaces/backfill")
async def backfill_spaces():
    """Register + L1-sync spaces for pre-existing datasource connections.

    The auto-register hook only fires on *new* connections; this endpoint
    backfills the ones created before the semantic center was deployed.
    """
    from dbgpt_serve.datasource.manages.connect_config_db import (
        ConnectConfigDao,
        ConnectConfigEntity,
    )

    dao = ConnectConfigDao()
    session = dao.get_raw_session()
    try:
        rows = session.query(ConnectConfigEntity).all()
        conns = [(r.db_name, r.db_type) for r in rows]
    finally:
        session.close()
    sync = SemanticSyncService()
    done: list = []
    failed: list = []
    for db_name, db_type in conns:
        try:
            sync.ensure_space(db_name, db_name, db_type or "")
            connector = _connector(db_name)
            sync.sync(db_name, connector)
            done.append(db_name)
        except Exception as e:  # noqa: BLE001 - one bad conn must not stop all
            logger.warning(f"backfill sync failed for {db_name}: {e}")
            failed.append(db_name)
    return Result.succ({"synced": done, "failed": failed})


@router.post("/v1/semantic/spaces/{ds_id}/drafts")
async def generate_drafts(ds_id: int, payload: Dict[str, Any] = Body(default={})):
    """Trigger L2 annotator + L3 miner + L4 join discovery.

    ``use_llm`` (default true) resolves the serving default model via the
    llm bridge; generation runs in a worker thread so the sync LLM adapter
    can own its event loop.
    """
    import asyncio

    service = get_semantic_service()
    space = service.get_space(ds_id)
    if not space:
        raise HTTPException(status_code=404, detail=f"space {ds_id} not found")
    llm = None
    if bool(payload.get("use_llm", True)):
        from dbgpt_serve.semantic.llm_bridge import build_sync_llm

        llm = await asyncio.to_thread(build_sync_llm)
    connector = None
    try:
        connector = _connector(str(space["conn_id"]))
    except Exception as e:  # noqa: BLE001 - FK discovery is best-effort
        logger.warning(f"connector unavailable for join discovery: {e}")
    result = await asyncio.to_thread(
        service.run_draft_generation, ds_id, llm, connector
    )
    return Result.succ(result)


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
@router.post("/v1/semantic/spaces/{ds_id}/examples")
async def create_example(ds_id: int, payload: Dict[str, Any] = Body(...)):
    return Result.succ(
        get_semantic_service().create_example(
            ds_id,
            payload,
            user=payload.get("user"),
            source=payload.get("source", "manual"),
        )
    )


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
