"""Persistent audit trail for tool approvals and policy changes.

Write points are synchronous with the security lifecycle (design doc §5.4):

- register            -> INSERT pending row (decision NULL)
- approval.intent     -> UPDATE intent bullets snapshot (what the user saw)
- resolve / ttl settle-> UPDATE decision/scope/reason/actor/settle_source

Failure policy: an audit write failure NEVER rolls back or blocks the safety
decision. The failed payload is queued in an in-memory compensation backlog
that flushes on the next successful write, and :func:`sweep_stale` marks
long-pending rows as ``expired_unresolved`` so gaps stay visible.
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt.storage.metadata import Model, db

logger = logging.getLogger(__name__)


class ToolApprovalLogEntity(Model):
    """One row per approval request, from register to decision."""

    __tablename__ = "tool_approval_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    approval_id = Column(String(64), unique=True, nullable=False, index=True)
    conv_id = Column(String(128), index=True, nullable=False)
    engine = Column(String(32), nullable=False, comment="dbgpt | pi")
    tool = Column(String(128), nullable=False)
    args_hash = Column(String(32), nullable=False)
    args_preview = Column(Text, nullable=True)
    rule_id = Column(String(128), nullable=False)
    risk = Column(String(16), nullable=False, comment="confirm | deny")
    intent_json = Column(Text, nullable=True, comment="bullets shown to the user")
    decision = Column(
        String(32), nullable=True, index=True, comment="NULL=pending"
    )
    scope = Column(String(16), nullable=True, comment="once | session | always")
    reason = Column(Text, nullable=True)
    actor = Column(String(128), nullable=True, comment="deciding user id")
    settle_source = Column(
        String(32), nullable=True, comment="rest | ttl | sweep"
    )
    ts_request = Column(DateTime, default=datetime.now, nullable=False)
    ts_decision = Column(DateTime, nullable=True)


class ApprovalPolicyLogEntity(Model):
    """Policy change diff audit (setting saves, toml bootstrap)."""

    __tablename__ = "approval_policy_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(128), nullable=True)
    source = Column(String(32), nullable=False, comment="setting | toml | bootstrap")
    diff_json = Column(Text, nullable=False)
    ts = Column(DateTime, default=datetime.now, nullable=False)


_TABLES = [ToolApprovalLogEntity.__table__, ApprovalPolicyLogEntity.__table__]

_init_lock = threading.Lock()
_initialized = False
_backlog: List[Any] = []
_backlog_lock = threading.Lock()


def _ensure_tables() -> None:
    """Create only the audit tables if missing (idempotent, no migration)."""
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


def _write(fn) -> None:
    """Run a DB write; compensate later on failure, never raise to caller."""
    try:
        _ensure_tables()
        with db.session() as session:
            fn(session)
            session.commit()
        _flush_backlog()
    except Exception:
        logger.critical(
            "approval audit write failed; queued for compensation", exc_info=True
        )
        with _backlog_lock:
            _backlog.append(fn)
            if len(_backlog) > 500:
                _backlog.pop(0)


def _flush_backlog() -> None:
    with _backlog_lock:
        pending = list(_backlog)
        _backlog.clear()
    for fn in pending:
        try:
            with db.session() as session:
                fn(session)
                session.commit()
        except Exception:
            logger.critical("approval audit compensation failed", exc_info=True)
            with _backlog_lock:
                _backlog.append(fn)


def audit_register(
    approval_id: str,
    conv_id: str,
    engine: str,
    tool: str,
    args_hash: str,
    args_preview: str,
    rule_id: str,
    risk: str,
) -> None:
    def w(session):
        exists = (
            session.query(ToolApprovalLogEntity)
            .filter(ToolApprovalLogEntity.approval_id == approval_id)
            .first()
        )
        if exists:
            return
        session.add(
            ToolApprovalLogEntity(
                approval_id=approval_id,
                conv_id=conv_id,
                engine=engine,
                tool=tool,
                args_hash=args_hash,
                args_preview=args_preview,
                rule_id=rule_id,
                risk=risk,
            )
        )

    _write(w)


def audit_intent(approval_id: str, intent_json: str) -> None:
    def w(session):
        row = (
            session.query(ToolApprovalLogEntity)
            .filter(ToolApprovalLogEntity.approval_id == approval_id)
            .first()
        )
        if row is not None:
            row.intent_json = intent_json

    _write(w)


def audit_decision(
    approval_id: str,
    decision: str,
    scope: Optional[str],
    reason: Optional[str],
    actor: Optional[str],
    settle_source: str,
) -> None:
    def w(session):
        row = (
            session.query(ToolApprovalLogEntity)
            .filter(ToolApprovalLogEntity.approval_id == approval_id)
            .first()
        )
        if row is None:
            # Register write was lost (crash before flush): reconstruct a
            # minimal row so the decision never exists without a trace.
            row = ToolApprovalLogEntity(
                approval_id=approval_id,
                conv_id="unknown",
                engine="unknown",
                tool="unknown",
                args_hash="unknown",
                rule_id="unknown",
                risk="unknown",
            )
            session.add(row)
        row.decision = decision
        row.scope = scope
        row.reason = reason
        row.actor = actor
        row.settle_source = settle_source
        row.ts_decision = datetime.now()

    _write(w)


def audit_policy_change(
    actor: Optional[str], source: str, diff: Dict[str, Any]
) -> None:
    def w(session):
        session.add(
            ApprovalPolicyLogEntity(
                actor=actor,
                source=source,
                diff_json=json.dumps(diff, ensure_ascii=False),
            )
        )

    _write(w)


def sweep_stale(ttl_seconds: float) -> int:
    """Mark long-pending rows as expired_unresolved; returns rows touched."""
    cutoff = datetime.now() - timedelta(seconds=ttl_seconds)
    touched = 0

    def w(session):
        nonlocal touched
        rows = (
            session.query(ToolApprovalLogEntity)
            .filter(ToolApprovalLogEntity.decision.is_(None))
            .filter(ToolApprovalLogEntity.ts_request < cutoff)
            .all()
        )
        for row in rows:
            row.decision = "expired_unresolved"
            row.settle_source = "sweep"
            row.ts_decision = datetime.now()
        touched = len(rows)

    try:
        _ensure_tables()
        with db.session() as session:
            w(session)
            session.commit()
    except Exception:
        logger.critical("approval audit sweep failed", exc_info=True)
    return touched


def query_approval_logs(
    conv_id: Optional[str] = None, limit: int = 50, offset: int = 0
) -> List[Dict[str, Any]]:
    _ensure_tables()
    with db.session() as session:
        q = session.query(ToolApprovalLogEntity)
        if conv_id:
            q = q.filter(ToolApprovalLogEntity.conv_id == conv_id)
        rows = (
            q.order_by(ToolApprovalLogEntity.id.desc()).offset(offset).limit(limit).all()
        )
        return [
            {
                "approval_id": r.approval_id,
                "conv_id": r.conv_id,
                "engine": r.engine,
                "tool": r.tool,
                "args_hash": r.args_hash,
                "args_preview": r.args_preview,
                "rule_id": r.rule_id,
                "risk": r.risk,
                "intent": r.intent_json,
                "decision": r.decision,
                "scope": r.scope,
                "reason": r.reason,
                "actor": r.actor,
                "settle_source": r.settle_source,
                "ts_request": r.ts_request.isoformat() if r.ts_request else None,
                "ts_decision": r.ts_decision.isoformat() if r.ts_decision else None,
            }
            for r in rows
        ]
