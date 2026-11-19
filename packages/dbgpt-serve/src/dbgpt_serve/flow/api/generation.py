"""Conversation editing routes, using the flow API's authentication boundary."""

import copy
import json
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from dbgpt._private.pydantic import Field
from dbgpt_serve.core import Result

from ..service.generation_service import (
    DraftRequest,
    GenerationService,
    MessageRequest,
    Scope,
    Snapshot,
    StrictModel,
    fingerprint,
    flow_fingerprint,
    validate_candidate,
)
from .endpoints import check_api_key, get_service
from .schemas import FlowDebugRequest, ServeRequest

router = APIRouter(prefix="/taskflow/generation-sessions")
_service: Optional[GenerationService] = None


def get_generation_service() -> GenerationService:
    global _service
    flow_service = get_service()
    if _service is None or _service.flow_service is not flow_service:
        _service = GenerationService(flow_service._system_app, flow_service)
    return _service


def get_owner(token: Optional[str] = Depends(check_api_key)) -> str:
    # Never store API keys or treat a client-supplied user header as identity.
    # Without configured API keys the existing application is single-instance.
    return fingerprint(token or "local-instance")


class CreateRequest(StrictModel):
    flow_uid: Optional[str] = None
    snapshot: Optional[Snapshot] = None


class RunRequest(StrictModel):
    expected_draft_revision: int
    model: str
    question: str = Field(min_length=1, max_length=20000)


class SaveRequest(StrictModel):
    expected_draft_revision: int
    publish: bool = False


def flow_payload(state: dict, publish: bool = False) -> ServeRequest:
    meta = state["snapshot"]["meta"]
    sid = state["session_id"]
    return ServeRequest(
        uid=meta.get("uid") or str(uuid.uuid4()),
        name=meta.get("name") or f"taskflow_{sid[:12]}",
        label=meta.get("label") or "未命名工作流",
        description=meta.get("description"),
        editable=True,
        state="deployed" if publish else "developing",
        flow_category="chat_flow",
        flow_format="taskflow",
        taskflow_source=state["snapshot"]["dsl"],
    )


def validate_snapshot(state: dict, catalog: dict) -> dict:
    try:
        return validate_candidate(
            state["snapshot"]["dsl"],
            state["snapshot"]["dsl"],
            Scope(),
            catalog,
            (state["candidate"] or {}).get("missing_configuration", []),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"流程配置不完整或无效：{exc}") from exc


@router.post("")
async def create(
    request: CreateRequest,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    if request.flow_uid:
        flow = service.flow_service.get({"uid": request.flow_uid})
        if not flow or not flow.taskflow_source:
            raise HTTPException(404, "TaskFlow 不存在")
        if not flow.editable:
            raise HTTPException(403, "工作流不可编辑")
        snapshot = {
            "dsl": flow.taskflow_source,
            "meta": {
                "uid": flow.uid,
                "name": flow.name,
                "label": flow.label,
                "description": flow.description,
                "state": flow.state,
            },
        }
    else:
        if request.snapshot is None:
            raise HTTPException(422, "缺少初始画布")
        snapshot = request.snapshot.model_dump()
        snapshot["meta"] = {
            k: v for k, v in snapshot["meta"].items() if k in {"label", "description"}
        }
    return Result.succ(service.store.create(owner, snapshot))


@router.get("/{sid}")
async def get(
    sid: str,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    return Result.succ(service.get(sid, owner))


@router.put("/{sid}/draft")
async def sync(
    sid: str,
    request: DraftRequest,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    return Result.succ(service.sync(sid, owner, request))


@router.post("/{sid}/messages")
async def message(
    sid: str,
    request: MessageRequest,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    return Result.succ(await service.submit(sid, owner, request))


@router.post("/{sid}/requests/{rid}/cancel")
async def cancel(
    sid: str,
    rid: str,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    return Result.succ(service.cancel(sid, owner, rid))


@router.post("/{sid}/candidates/{cid}/{action}")
async def candidate_action(
    sid: str,
    cid: str,
    action: str,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    if action not in {"apply", "discard"}:
        raise HTTPException(404, "操作不存在")
    try:
        return Result.succ(await service.candidate_action(sid, owner, cid, action))
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"候选配置无效：{exc}") from exc


@router.post("/{sid}/undo")
async def undo(
    sid: str,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    return Result.succ(service.undo(sid, owner))


@router.post("/{sid}/debug")
async def debug(
    sid: str,
    request: RunRequest,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    catalog = await service.catalog()
    state, version = service.store.read(sid, owner)
    if request.expected_draft_revision != state["draft_revision"]:
        raise HTTPException(409, "画布已改变，请同步后试运行")
    if state["candidate"] and state["candidate"]["status"] == "pending":
        raise HTTPException(409, "请先应用或放弃候选")
    validation = validate_snapshot(state, catalog)
    if validation["missing_configuration"]:
        raise HTTPException(422, validation["missing_configuration"])
    if request.model not in catalog["models"]:
        raise HTTPException(422, "试运行模型不可用")
    run = {
        "run_id": uuid.uuid4().hex,
        "draft_revision": state["draft_revision"],
        "snapshot_fingerprint": fingerprint(state["snapshot"]),
        "catalog_version": fingerprint(catalog),
        "model": request.model,
        "question": request.question,
        "status": "running",
    }
    state["run"] = run
    service.store.write(state, owner, version)
    debug_request = FlowDebugRequest(
        flow=flow_payload(state),
        request={
            "model": request.model,
            "messages": request.question,
            "stream": False,
            "conv_uid": f"taskflow-debug-{run['run_id']}",
        },
    )

    async def stream():
        success = False
        failed = False
        seen_output = False
        markers = {}
        expected_steps = {
            n["id"]
            for n in state["snapshot"]["dsl"]["nodes"]
            if n["kind"] not in {"start", "output"}
        }
        try:
            async for output in service.flow_service.debug_flow(
                debug_request, default_incremental=False
            ):
                if output.error_code:
                    failed = True
                    yield (
                        "data:"
                        + json.dumps({"error": output.text}, ensure_ascii=False)
                        + "\n\n"
                    )
                    break
                if output.text:
                    seen_output = True
                    for block in re.findall(
                        r"```vis-flow-step\s*\n(.*?)```", output.text, re.S
                    ):
                        try:
                            marker = json.loads(block)
                            markers[marker["step_id"]] = marker["status"]
                        except (ValueError, KeyError):
                            failed = True
                    yield (
                        "data:"
                        + json.dumps({"text": output.text}, ensure_ascii=False)
                        + "\n\n"
                    )
            success = (
                seen_output
                and not failed
                and bool(expected_steps)
                and all(markers.get(nid) == "success" for nid in expected_steps)
            )
        except Exception as exc:
            yield "data:" + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
        finally:
            latest, current_version = service.store.read(sid, owner)
            if (
                latest["run"]
                and latest["run"]["run_id"] == run["run_id"]
                and latest["draft_revision"] == run["draft_revision"]
            ):
                latest["run"]["status"] = "success" if success else "failed"
                service.store.write(latest, owner, current_version)
        yield (
            "data:"
            + json.dumps(
                {"run_completed": True, "success": success, "run_id": run["run_id"]}
            )
            + "\n\n"
        )

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/{sid}/save")
async def save(
    sid: str,
    request: SaveRequest,
    owner: str = Depends(get_owner),
    service: GenerationService = Depends(get_generation_service),
):
    catalog = await service.catalog()
    state, version = service.store.read(sid, owner)
    if state["draft_revision"] != request.expected_draft_revision:
        raise HTTPException(409, "画布已改变")
    if state["candidate"] and state["candidate"]["status"] == "pending":
        raise HTTPException(409, "候选尚未应用，请先处理候选")
    validation = validate_snapshot(state, catalog)
    if request.publish:
        if validation["missing_configuration"]:
            raise HTTPException(422, "请补齐资源配置")
        run = state["run"]
        if (
            not run
            or run["status"] != "success"
            or run["draft_revision"] != state["draft_revision"]
            or run["snapshot_fingerprint"] != fingerprint(state["snapshot"])
            or run["catalog_version"] != fingerprint(catalog)
        ):
            raise HTTPException(409, "请先对当前版本成功试运行，再发布")
    flow = flow_payload(state, request.publish)
    existing = service.flow_service.get({"uid": flow.uid})
    if request.publish:
        if existing and state["flow_base_fingerprint"] != flow_fingerprint(
            existing.taskflow_source,
            {
                "name": existing.name,
                "label": existing.label,
                "description": existing.description,
            },
        ):
            raise HTTPException(409, "已保存流程被其他编辑会话修改，请重新加载后核对")
        # Record the previous immutable definition before updating the alias.
        if existing and existing.state in {"deployed", "running"}:
            state["published"].append(
                {
                    "snapshot": {
                        "dsl": existing.taskflow_source,
                        "meta": {
                            "uid": existing.uid,
                            "name": existing.name,
                            "label": existing.label,
                            "description": existing.description,
                        },
                    }
                }
            )
        if existing:
            saved = service.flow_service.update_flow(flow)
        else:
            saved = service.flow_service.create_and_save_dag(flow)
        state["published"].append(
            {
                "snapshot": copy.deepcopy(state["snapshot"]),
                "run": copy.deepcopy(state["run"]),
            }
        )
    elif existing and existing.state in {"deployed", "running"}:
        # Saving an edit checkpoint never updates/unregisters the live DAG.
        saved = existing
    else:
        # A formal draft appears in the flow list but does not register a DAG.
        service.flow_service._maybe_compile_taskflow(flow)
        if existing:
            service.flow_service.dao.update({"uid": flow.uid}, flow)
        else:
            service.flow_service.dao.create(flow)
        # BaseDao.create queries by the full request and may return None even
        # after insertion. Use the stable identity, as the normal flow service does.
        saved = service.flow_service.get({"uid": flow.uid})
        if saved is None:
            raise HTTPException(500, "草稿已写入但未能回读，请重试")
    state["snapshot"]["meta"].update(
        uid=saved.uid,
        name=saved.name,
        state="deployed" if request.publish else "developing",
    )
    state["identity"] = {
        key: state["snapshot"]["meta"][key] for key in ("uid", "name", "state")
    }
    state["dirty"] = False
    if request.publish or not existing or existing.state not in {"deployed", "running"}:
        state["flow_base_fingerprint"] = flow_fingerprint(
            state["snapshot"]["dsl"], state["snapshot"]["meta"]
        )
    # Saving assigns an identity, but does not invalidate content validation.
    if state["run"]:
        state["run"]["snapshot_fingerprint"] = fingerprint(state["snapshot"])
    service.store.write(state, owner, version)
    return Result.succ(state)
