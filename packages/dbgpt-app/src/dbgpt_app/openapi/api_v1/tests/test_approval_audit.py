"""Tests for the approval audit trail (write points, compensation, sweep)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool

import dbgpt_app.openapi.api_v1.approval_audit as aa
from dbgpt.storage.metadata import db


@pytest.fixture()
def audit_db(monkeypatch):
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    monkeypatch.setattr(aa, "_initialized", True)
    monkeypatch.setattr(aa, "_backlog", [])
    yield


def test_register_intent_decision_query_roundtrip(audit_db):
    aa.audit_register(
        "apr_1",
        "conv_1",
        "dbgpt",
        "shell_interpreter",
        "hash1",
        "pkill x",
        "r",
        "confirm",
    )
    rows = aa.query_approval_logs("conv_1")
    assert len(rows) == 1 and rows[0]["decision"] is None

    aa.audit_intent("apr_1", '["将**强制终止**匹配进程"]')
    aa.audit_decision("apr_1", "approved", "session", None, "user_9", "rest")

    rows = aa.query_approval_logs("conv_1")
    assert rows[0]["decision"] == "approved"
    assert rows[0]["scope"] == "session"
    assert rows[0]["actor"] == "user_9"
    assert rows[0]["settle_source"] == "rest"
    assert "强制终止" in rows[0]["intent"]
    assert rows[0]["ts_decision"] is not None
    # other conversations stay isolated
    assert aa.query_approval_logs("conv_other") == []


def test_failed_write_is_compensated_on_next_success(audit_db, monkeypatch):
    real_ensure = aa._ensure_tables
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("db down")
        return real_ensure()

    monkeypatch.setattr(aa, "_ensure_tables", flaky)
    aa.audit_register("apr_lost", "conv_1", "pi", "sql_query", "h", "q", "r", "confirm")
    assert len(aa._backlog) == 1
    assert aa.query_approval_logs("conv_1") == []

    monkeypatch.setattr(aa, "_ensure_tables", real_ensure)
    aa.audit_register("apr_ok", "conv_1", "pi", "sql_query", "h2", "q2", "r", "confirm")
    ids = {r["approval_id"] for r in aa.query_approval_logs("conv_1")}
    assert ids == {"apr_lost", "apr_ok"}
    assert aa._backlog == []


def test_decision_without_register_reconstructs_row(audit_db):
    aa.audit_decision("apr_ghost", "rejected", "once", "no", "u1", "rest")
    rows = aa.query_approval_logs(None)
    assert len(rows) == 1
    assert rows[0]["decision"] == "rejected"
    assert rows[0]["conv_id"] == "unknown"


def test_sweep_marks_stale_pending(audit_db):
    aa.audit_register(
        "apr_old", "conv_1", "dbgpt", "shell_interpreter", "h", "c", "r", "confirm"
    )
    with db.session() as session:
        row = (
            session.query(aa.ToolApprovalLogEntity)
            .filter_by(approval_id="apr_old")
            .first()
        )
        row.ts_request = datetime.now() - timedelta(seconds=600)
        session.commit()
    assert aa.sweep_stale(60) == 1
    rows = aa.query_approval_logs("conv_1")
    assert rows[0]["decision"] == "expired_unresolved"
    assert rows[0]["settle_source"] == "sweep"
    # settled rows are never swept
    assert aa.sweep_stale(60) == 0


def test_policy_change_log(audit_db):
    aa.audit_policy_change(
        "admin", "setting", {"rule": ["sql.dml_write: confirm→deny"]}
    )
    with db.session() as session:
        got = [
            (r.source, r.diff_json)
            for r in session.query(aa.ApprovalPolicyLogEntity).all()
        ]
    assert len(got) == 1
    assert got[0][0] == "setting"
    assert "confirm→deny" in got[0][1]
