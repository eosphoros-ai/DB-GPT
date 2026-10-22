"""L2 policy store for tool approval (setting page backend).

Implements design doc §4.4-§4.7: the product setting layer sits above the
builtin rule table (L0) and toml/env (L1); merges are hot-reloaded via a
short-TTL cache keyed on table timestamps (multi-instance push is P2).

Endpoints (registered onto the agentic router):
- GET  /v1/chat/approval/policy            current merged view + version
- POST /v1/chat/approval/policy/save       batch save with audit diff
- POST /v1/chat/approval/policy/playground dry-run classify trace
- GET  /v1/chat/approval/whitelist         session/always memory entries
- POST /v1/chat/approval/whitelist/revoke  revoke one memory entry
- GET  /v1/chat/approval/session-mode      per-conversation permission mode
- POST /v1/chat/approval/session-mode      set default | strict | open
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query
from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt._private.pydantic import BaseModel
from dbgpt.storage.metadata import Model, db

from .approval_audit import audit_policy_change
from .tool_names import canonical_tool

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 5.0
_VALID_TIERS = ("auto", "confirm", "deny")


class ApprovalPolicyRuleEntity(Model):
    """L2 rules and per-tool tier overrides (arg_pattern NULL = override)."""

    __tablename__ = "approval_policy_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(16), nullable=False, comment="rule | override")
    tool = Column(String(128), nullable=False)
    arg_pattern = Column(Text, nullable=True, comment="regex; NULL on overrides")
    tier = Column(String(16), nullable=False)
    locked = Column(Integer, default=0, comment="1 = managed, cannot relax/delete")
    source = Column(String(32), default="setting")
    updated_by = Column(String(128), nullable=True)
    updated_ts = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    active = Column(Integer, default=1)


class ApprovalPolicySettingEntity(Model):
    """Scalar policy params (mode / ttl / intent / fail_safe)."""

    __tablename__ = "approval_policy_setting"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_by = Column(String(128), nullable=True)
    updated_ts = Column(DateTime, default=datetime.now, onupdate=datetime.now)


_TABLES = [ApprovalPolicyRuleEntity.__table__, ApprovalPolicySettingEntity.__table__]
_init_lock = threading.Lock()
_initialized = False
_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


def _ensure_tables() -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        engine = getattr(db, "engine", None) or getattr(db, "_engine", None)
        if engine is None:
            raise RuntimeError("metadata db not initialized")
        Model.metadata.create_all(engine, tables=_TABLES)
        _initialized = True


def invalidate_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _snapshot() -> Dict[str, Any]:
    """Cached plain-dict view of the L2 tables (TTL + write invalidation)."""
    with _cache_lock:
        if _cache and time.time() - _cache["ts"] < _CACHE_TTL_SECONDS:
            return _cache
    rules: List[Dict[str, Any]] = []
    overrides: List[Dict[str, Any]] = []
    settings: Dict[str, str] = {}
    stamp = 0.0
    try:
        _ensure_tables()
        with db.session() as session:
            for row in (
                session.query(ApprovalPolicyRuleEntity).filter_by(active=1).all()
            ):
                item = {
                    "id": row.id,
                    "kind": row.kind,
                    "tool": row.tool,
                    "arg_pattern": row.arg_pattern,
                    "tier": row.tier,
                    "locked": bool(row.locked),
                    "source": row.source,
                    "updated_by": row.updated_by,
                }
                (overrides if row.kind == "override" else rules).append(item)
                if row.updated_ts:
                    stamp = max(stamp, row.updated_ts.timestamp())
            for row in session.query(ApprovalPolicySettingEntity).all():
                settings[row.key] = row.value or ""
                if row.updated_ts:
                    stamp = max(stamp, row.updated_ts.timestamp())
    except Exception:
        # No metadata db in this process (unit tests, standalone tools):
        # fall back to builtin-only policy instead of breaking every gate.
        logger.warning("approval policy store unavailable; builtin-only policy")
        snap = {
            "rules": [],
            "overrides": [],
            "settings": {},
            "stamp": 0.0,
            "ts": time.time(),
        }
        with _cache_lock:
            _cache.clear()
            _cache.update(snap)
        return snap
    snap = {
        "rules": rules,
        "overrides": overrides,
        "settings": settings,
        "stamp": stamp,
        "ts": time.time(),
    }
    with _cache_lock:
        _cache.clear()
        _cache.update(snap)
    return snap


def dynamic_rules() -> List[Dict[str, Any]]:
    """L2 rule rows (caller converts to ApprovalRule; listed before builtin)."""
    return [r for r in _snapshot()["rules"]]


def tool_override(tool: str) -> Optional[str]:
    wanted = canonical_tool(tool)
    for ov in _snapshot()["overrides"]:
        if canonical_tool(ov["tool"]) == wanted:
            return ov["tier"]
    return None


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    value = _snapshot()["settings"].get(key)
    return value if value not in (None, "") else default


# ── per-conversation permission mode (composer badge) ──────────────────────
# Persisted as setting rows keyed ``conv_mode:<conv_uid>`` so a conversation
# keeps its mode across backend restarts; brand-new conversations have no row
# and start at ``default``.
CONV_MODES = ("default", "strict", "open")
_CONV_MODE_PREFIX = "conv_mode:"


def get_conv_mode(conv_id: str) -> str:
    if not conv_id:
        return "default"
    return get_setting(f"{_CONV_MODE_PREFIX}{conv_id}", "default") or "default"


def set_conv_mode(conv_id: str, mode: str) -> str:
    """Upsert the persisted mode; ``default`` deletes the row."""
    mode = (mode or "default").strip().lower()
    if mode not in CONV_MODES:
        raise ValueError(f"unknown conversation approval mode: {mode}")
    if not conv_id:
        raise ValueError("conv_id is required")
    key = f"{_CONV_MODE_PREFIX}{conv_id}"
    _ensure_tables()
    with db.session() as session:
        row = session.query(ApprovalPolicySettingEntity).filter_by(key=key).first()
        if mode == "default":
            if row is not None:
                session.delete(row)
        elif row is None:
            session.add(ApprovalPolicySettingEntity(key=key, value=mode))
        else:
            row.value = mode
            row.updated_ts = datetime.now()
    invalidate_cache()
    return mode


def whitelist_view(center, conv_id: Optional[str]) -> List[Dict[str, Any]]:
    entries = [
        {"scope": "always", "signature": sig, "conv_id": None}
        for sig in sorted(center._always_allow)
    ]
    if conv_id:
        entries += [
            {"scope": "session", "signature": sig, "conv_id": conv_id}
            for sig in sorted(center._session_allow.get(conv_id, set()))
        ]
    return entries


# ── endpoints ───────────────────────────────────────────────────────────────


class _PolicySaveBody(BaseModel):
    mode: Optional[str] = None
    ttl_seconds: Optional[int] = None
    intent_analysis: Optional[bool] = None
    fail_safe: Optional[str] = None
    tool_overrides: Optional[List[Dict[str, Any]]] = None
    add_rules: Optional[List[Dict[str, Any]]] = None
    delete_rule_ids: Optional[List[int]] = None


def register_approval_policy_endpoints(router: APIRouter) -> None:
    from fastapi import Depends

    from dbgpt_app.openapi.api_v1.agentic_data_api import (  # noqa: F401
        Result,
        UserRequest,
        get_user_from_headers,
    )

    @router.get("/v1/chat/approval/policy")
    async def approval_policy_view(
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        from .approval import approval_mode, approval_ttl_seconds

        snap = _snapshot()
        return Result.succ(
            {
                "mode": approval_mode(),
                "ttl_seconds": int(approval_ttl_seconds()),
                "intent_analysis": get_setting("intent_analysis", "true") != "false",
                "fail_safe": get_setting("fail_safe", "confirm"),
                "tool_overrides": snap["overrides"],
                "rules": snap["rules"],
                "version": snap["stamp"],
            }
        )

    @router.post("/v1/chat/approval/policy/playground")
    async def approval_playground(
        payload: Dict[str, Any] = Body(),
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        from .approval import POLICY

        tool = str(payload.get("tool") or "")
        text = str(payload.get("text") or "")
        if not tool:
            return Result.failed(msg="tool is required")
        verdict, trace = POLICY.classify_trace(tool, {"command": text, "query": text})
        return Result.succ({"verdict": verdict, "trace": trace})

    @router.post("/v1/chat/approval/policy/save")
    async def approval_policy_save(
        body: _PolicySaveBody,
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        actor = user_token.user_id if user_token else None
        diff: Dict[str, Any] = {}
        snap = _snapshot()
        locked_override_tools = {ov["tool"] for ov in snap["overrides"] if ov["locked"]}
        locked_rule_ids = {r["id"] for r in snap["rules"] if r["locked"]}
        # ── validate everything BEFORE opening a write session: db.session()
        # commits on exit, so a mid-write failure must never persist half a
        # save.
        if body.mode is not None and body.mode not in ("off", "tiered", "always"):
            return Result.failed(msg=f"invalid mode: {body.mode}")
        if body.fail_safe is not None and body.fail_safe not in ("confirm", "auto"):
            return Result.failed(msg=f"invalid fail_safe: {body.fail_safe}")
        for ov in body.tool_overrides or []:
            if str(ov.get("tier") or "") not in _VALID_TIERS + ("rules",):
                return Result.failed(msg=f"invalid tier: {ov.get('tier')}")
            if ov.get("tool") in locked_override_tools:
                return Result.failed(
                    msg=f"override for {ov.get('tool')} is managed-locked"
                )
        for add in body.add_rules or []:
            tool = str(add.get("tool") or "")
            tier = str(add.get("tier") or "")
            pattern = str(add.get("arg_pattern") or "").strip()
            if tier not in _VALID_TIERS or not tool or not pattern:
                return Result.failed(msg="invalid rule payload")
        for rid in body.delete_rule_ids or []:
            if int(rid) in locked_rule_ids:
                return Result.failed(msg=f"rule {rid} is managed-locked")
        try:
            _ensure_tables()
            with db.session() as session:
                scalars: Dict[str, Any] = {
                    "mode": body.mode,
                    "ttl_seconds": body.ttl_seconds,
                    "intent_analysis": body.intent_analysis,
                    "fail_safe": body.fail_safe,
                }
                for key, value in scalars.items():
                    if value is None:
                        continue
                    text = str(value).lower() if isinstance(value, bool) else str(value)
                    row = (
                        session.query(ApprovalPolicySettingEntity)
                        .filter_by(key=key)
                        .first()
                    )
                    old = row.value if row else None
                    if row is None:
                        row = ApprovalPolicySettingEntity(key=key)
                        session.add(row)
                    row.value = text
                    row.updated_by = actor
                    row.updated_ts = datetime.now()
                    diff[key] = {"old": old, "new": text}
                for ov in body.tool_overrides or []:
                    tool, tier = str(ov.get("tool") or ""), str(ov.get("tier") or "")
                    row = (
                        session.query(ApprovalPolicyRuleEntity)
                        .filter_by(kind="override", tool=tool, active=1)
                        .first()
                    )
                    if tier == "rules":
                        if row is not None:
                            row.active = 0
                            row.updated_ts = datetime.now()
                        diff[f"override:{tool}"] = {
                            "old": row.tier if row else None,
                            "new": None,
                        }
                        continue
                    if row is None:
                        row = ApprovalPolicyRuleEntity(kind="override", tool=tool)
                        session.add(row)
                    old = row.tier
                    row.tier = tier
                    row.source = "setting"
                    row.updated_by = actor
                    row.updated_ts = datetime.now()
                    diff[f"override:{tool}"] = {"old": old, "new": tier}
                for add in body.add_rules or []:
                    session.add(
                        ApprovalPolicyRuleEntity(
                            kind="rule",
                            tool=str(add.get("tool") or ""),
                            arg_pattern=str(add.get("arg_pattern") or "").strip(),
                            tier=str(add.get("tier") or ""),
                            source="setting",
                            updated_by=actor,
                            updated_ts=datetime.now(),
                        )
                    )
                    diff[f"rule+:{add.get('tool')}:{add.get('arg_pattern')}"] = {
                        "old": None,
                        "new": add.get("tier"),
                    }
                for rid in body.delete_rule_ids or []:
                    row = session.query(ApprovalPolicyRuleEntity).get(int(rid))
                    if row is None:
                        continue
                    row.active = 0
                    row.updated_ts = datetime.now()
                    diff[f"rule-:{row.tool}:{row.arg_pattern}"] = {
                        "old": row.tier,
                        "new": None,
                    }
        except Exception as e:
            logger.exception("approval policy save failed")
            return Result.failed(msg=str(e))
        invalidate_cache()
        if diff:
            audit_policy_change(actor, "setting", diff)
        return Result.succ({"version": _snapshot()["stamp"], "diff": diff})

    @router.get("/v1/chat/approval/whitelist")
    async def approval_whitelist(
        con_uid: Optional[str] = Query(default=None),
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        from .approval import approval_center

        return Result.succ(whitelist_view(approval_center, con_uid))

    @router.post("/v1/chat/approval/whitelist/revoke")
    async def approval_whitelist_revoke(
        payload: Dict[str, Any] = Body(),
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        from .approval import approval_center

        scope = str(payload.get("scope") or "")
        signature = str(payload.get("signature") or "")
        conv_id = payload.get("conv_id")
        actor = user_token.user_id if user_token else None
        ok = approval_center.revoke(scope, signature, conv_id)
        if ok:
            audit_policy_change(
                actor,
                "setting",
                {"whitelist_revoke": {"scope": scope, "signature": signature}},
            )
        return Result.succ({"success": ok})

    @router.get("/v1/chat/approval/session-mode")
    async def approval_session_mode(
        con_uid: Optional[str] = Query(default=None),
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        """Per-conversation permission mode shown by the composer badge."""
        from .approval import approval_center

        return Result.succ(
            {"con_uid": con_uid, "mode": approval_center.conv_mode(con_uid or "")}
        )

    @router.post("/v1/chat/approval/session-mode")
    async def approval_session_mode_set(
        payload: Dict[str, Any] = Body(),
        user_token: UserRequest = Depends(get_user_from_headers),
    ):
        """Set the per-conversation mode: default | strict | open."""
        from .approval import approval_center

        conv_id = str(payload.get("con_uid") or payload.get("conv_id") or "").strip()
        mode = str(payload.get("mode") or "default").strip().lower()
        if not conv_id:
            return Result.failed(msg="con_uid is required")
        if mode not in approval_center.CONV_MODES:
            return Result.failed(msg=f"invalid mode: {mode}")
        old = approval_center.conv_mode(conv_id)
        approval_center.set_conv_mode(conv_id, mode)
        audit_policy_change(
            user_token.user_id if user_token else None,
            "session-mode",
            {"session_mode": {"con_uid": conv_id, "old": old, "new": mode}},
        )
        return Result.succ({"con_uid": conv_id, "mode": mode})
