"""Tests for the L2 approval policy store (setting page backend)."""

import asyncio

import pytest
from sqlalchemy.pool import StaticPool

import dbgpt_app.openapi.api_v1.approval as approval_mod
import dbgpt_app.openapi.api_v1.approval_policy as ap
from dbgpt.storage.metadata import db
from dbgpt_app.openapi.api_v1.approval import POLICY, ApprovalCenter


@pytest.fixture()
def policy_db(monkeypatch):
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    monkeypatch.setattr(ap, "_initialized", True)
    ap.invalidate_cache()
    yield
    ap.invalidate_cache()


def _add_rule(kind, tool, tier, pattern=None, locked=False):
    with db.session() as session:
        row = ap.ApprovalPolicyRuleEntity(
            kind=kind,
            tool=tool,
            tier=tier,
            arg_pattern=pattern,
            locked=1 if locked else 0,
        )
        session.add(row)
        session.commit()
        rid = row.id
    ap.invalidate_cache()
    return rid


def test_setting_rule_beats_builtin_within_tier(policy_db):
    rid = _add_rule("rule", "shell_interpreter", "deny", pattern=r"uv\s+run\s+deploy")
    tier, rule_id = POLICY.classify(
        "shell_interpreter", {"command": "uv run deploy prod"}
    )
    assert tier == "deny" and rule_id == f"setting:{rid}"
    # builtin still applies to other commands
    assert POLICY.classify("shell_interpreter", {"command": "ls"})[0] == "auto"


def test_tool_override_forces_tier_but_denies_still_win(policy_db):
    _add_rule("override", "shell_interpreter", "auto")
    # confirm-tier builtin relaxed by override
    assert POLICY.classify("shell_interpreter", {"command": "pkill x"})[0] == "auto"
    # deny matches can never be relaxed
    assert POLICY.classify("shell_interpreter", {"command": "rm -rf /"})[0] == "deny"
    # override tightens read-only tools too
    _add_rule("override", "kb_ls", "confirm")
    assert POLICY.classify("kb_ls", {"space": "x"})[0] == "confirm"


def test_classify_trace_reports_hits_and_override(policy_db):
    _add_rule("override", "sql_query", "deny")
    verdict, trace = POLICY.classify_trace("sql_query", {"query": "SELECT 1"})
    assert verdict == ("deny", "setting.override")
    assert any(t["rule_id"] == "setting.override" and t["hit"] for t in trace)
    # builtin auto rule matched but lost to the forced override
    assert any(t["rule_id"] == "sql.read" and t["hit"] for t in trace)
    assert any(t["rule_id"] == "shell.readonly" and not t["hit"] for t in trace)


def test_save_endpoint_batch_diff_and_lock(policy_db):
    from fastapi import APIRouter

    router = APIRouter()
    ap.register_approval_policy_endpoints(router)
    endpoints = {r.path: r.endpoint for r in router.routes}
    save = endpoints["/v1/chat/approval/policy/save"]
    view = endpoints["/v1/chat/approval/policy"]

    locked_id = _add_rule("rule", "web_fetch", "confirm", pattern=r"x", locked=True)

    body = ap._PolicySaveBody(
        mode="tiered",
        ttl_seconds=120,
        tool_overrides=[{"tool": "code_interpreter", "tier": "confirm"}],
        add_rules=[
            {
                "tool": "shell_interpreter",
                "arg_pattern": "pytest -k slow",
                "tier": "auto",
            }
        ],
        delete_rule_ids=[locked_id],
    )
    result = asyncio.run(save(body=body, user_token=None))
    # locked rule deletion must fail the whole save
    assert result.success is False or result.err_code is not None

    body2 = ap._PolicySaveBody(
        ttl_seconds=120,
        tool_overrides=[{"tool": "code_interpreter", "tier": "confirm"}],
        add_rules=[
            {
                "tool": "shell_interpreter",
                "arg_pattern": "pytest -k slow",
                "tier": "auto",
            }
        ],
    )
    result2 = asyncio.run(save(body=body2, user_token=None))
    assert result2.err_code is None
    diff = result2.data["diff"]
    assert diff["ttl_seconds"]["new"] == "120"
    assert diff["override:code_interpreter"]["new"] == "confirm"

    # effect visible through classify + view endpoint
    assert POLICY.classify("code_interpreter", {"code": "print(1)"})[0] == "confirm"
    assert (
        POLICY.classify("shell_interpreter", {"command": "pytest -k slow"})[0] == "auto"
    )
    viewed = asyncio.run(view(user_token=None))
    assert viewed.data["ttl_seconds"] == 120
    assert approval_mod.approval_ttl_seconds() == 120.0


def test_whitelist_revoke(policy_db):
    center = ApprovalCenter()
    center.remember("c1", "session", "shell_interpreter", {"command": "uv run pytest"})
    center.remember("c1", "always", "sql_query", {"query": "SELECT 1"})
    sig_session = center.signature("shell_interpreter", {"command": "uv run pytest"})
    sig_always = center.signature("sql_query", {"query": "SELECT 1"})
    entries = ap.whitelist_view(center, "c1")
    assert {e["signature"] for e in entries} == {sig_session, sig_always}
    assert center.revoke("session", sig_session, "c1") is True
    assert center.revoke("session", sig_session, "c1") is False
    assert center.revoke("always", sig_always) is True
    assert not center.is_allowed("c1", "sql_query", {"query": "SELECT 1"})
