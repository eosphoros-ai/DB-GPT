"""Human-in-the-loop tool approval (high-risk gate) for agentic chats.

P0 slice of ``docs/design/tool-approval-design.md``:

- :class:`ToolRiskPolicy` — builtin rule table (auto / confirm / deny) with
  env-overridable global mode (``DBGPT_APPROVAL_MODE``).
- :class:`ApprovalCenter` — register / wait / resolve with TTL auto-reject and
  session / always scope allowlists (signature = sha1(tool + args)).
- :func:`make_approval_gate` — closure installed into
  ``dbgpt.agent.expand.actions.tool_action.set_current_tool_gate``; emits
  ``approval.requested`` / ``approval.resolved`` SSE events via the round's
  stream callback and returns reject / deny observations to the model.

REST endpoints (resolve / pending) live next to the question endpoints in
``agentic_data_api.py`` and use the module-level ``approval_center`` singleton.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TIER_AUTO = "auto"
TIER_CONFIRM = "confirm"
TIER_DENY = "deny"
_TIER_RANK = {TIER_DENY: 0, TIER_CONFIRM: 1, TIER_AUTO: 2}

# Tools whose unmatched calls fail safe to ``confirm`` instead of ``auto``.
GATED_TOOLS = {"shell_interpreter", "code_interpreter", "sql_query", "web_fetch"}

_PRIMARY_ARG_KEYS = (
    "command",
    "code",
    "query",
    "sql",
    "statement",
    "url",
    "path",
    "cmd",
)


def approval_mode() -> str:
    """Global mode: ``off`` | ``tiered`` (default) | ``always``."""
    return os.environ.get("DBGPT_APPROVAL_MODE", "tiered").strip().lower()


def approval_ttl_seconds() -> float:
    return float(os.environ.get("DBGPT_APPROVAL_TTL_SECONDS", "300"))


def _args_blob(args: Any) -> str:
    """Human-meaningful string form of tool args for pattern matching."""
    if not isinstance(args, dict):
        return str(args)
    for key in _PRIMARY_ARG_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    parts = [v for v in args.values() if isinstance(v, str) and v.strip()]
    if parts:
        return "\n".join(parts)
    return json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)


def _sql_text(args: dict) -> str:
    for key in ("query", "sql", "statement"):
        value = args.get(key)
        if isinstance(value, str):
            return value.strip()
    return ""


def _is_write_without_where(args: dict) -> bool:
    sql = _sql_text(args)
    if not re.match(r"^(update|delete)\b", sql, re.IGNORECASE):
        return False
    return not re.search(r"\bwhere\b", sql, re.IGNORECASE)


def _is_write_with_where(args: dict) -> bool:
    sql = _sql_text(args)
    if re.match(r"^insert\b", sql, re.IGNORECASE):
        return True
    if not re.match(r"^(update|delete)\b", sql, re.IGNORECASE):
        return False
    return re.search(r"\bwhere\b", sql, re.IGNORECASE) is not None


# ── shell command composition analysis ─────────────────────────────────────
# Plain regex over the raw command string is evadable (composition,
# encodings, indirect exec). Two structural checks harden the auto tier:
# a command only auto-passes when *every* segment of a pipeline/chain is a
# read-only command; anything composed that isn't fully read-only falls to
# the confirm tier via ``shell.composed``.
_READONLY_CMD_RE = re.compile(
    r"^\s*(ls|cat|grep|ps|df|du|tail|head|wc|pwd|echo|pytest|uv run pytest|"
    r"git (status|log|diff|show|branch)|find|which|whereis|env|printenv|"
    r"date|whoami|id|uname|hostname|jq|tree|stat|file)\b",
    re.IGNORECASE,
)
_COMPOSE_RE = re.compile(r"[|;&]+|\$\(|`")


def _command_segments(blob: str) -> List[str]:
    return [s for s in _COMPOSE_RE.split(blob) if s and s.strip()]


def _is_readonly_pipeline(args: dict) -> bool:
    blob = _args_blob(args)
    if not blob.strip():
        return False
    segments = _command_segments(blob)
    return bool(segments) and all(
        _READONLY_CMD_RE.match(seg.strip()) for seg in segments
    )


def _is_composed(args: dict) -> bool:
    blob = _args_blob(args)
    if not _COMPOSE_RE.search(blob):
        return False
    return not _is_readonly_pipeline(args)


@dataclass(frozen=True)
class ApprovalRule:
    """One policy rule: tool scope + arg predicate -> tier."""

    rule_id: str
    tool: str
    tier: str
    pattern: Optional[str] = None
    pred: Optional[Callable[[dict], bool]] = None
    source: str = "builtin"

    def matches(self, tool: str, args: dict, blob: str) -> bool:
        if self.tool != "*" and self.tool != tool:
            return False
        if self.pred is not None:
            try:
                return bool(self.pred(args))
            except Exception:  # never let a bad predicate crash the gate
                logger.exception("approval rule %s predicate failed", self.rule_id)
                return False
        if self.pattern is None:
            return True
        return re.search(self.pattern, blob, re.IGNORECASE) is not None


BUILTIN_RULES: List[ApprovalRule] = [
    # ── deny tier (evaluated first) ─────────────────────────────────────────
    ApprovalRule(
        "shell.mass_kill",
        "shell_interpreter",
        TIER_DENY,
        pattern=r"rm\s+-rf\s+(/|~|\*)(\s|$)",
    ),
    ApprovalRule(
        "shell.pipe_exec",
        "shell_interpreter",
        TIER_DENY,
        pattern=r"(curl|wget)[^\n]*\|\s*(sh|bash|zsh)",
    ),
    ApprovalRule("shell.mkfs", "shell_interpreter", TIER_DENY, pattern=r"\bmkfs\b"),
    ApprovalRule(
        "shell.dd_device",
        "shell_interpreter",
        TIER_DENY,
        pattern=r"\bdd\b[^\n]*of=/dev/",
    ),
    ApprovalRule(
        "shell.chmod_root",
        "shell_interpreter",
        TIER_DENY,
        pattern=r"chmod\s+(-R\s+)?777\s+(/|~)(\s|$)",
    ),
    ApprovalRule(
        "shell.fork_bomb", "shell_interpreter", TIER_DENY, pattern=r":\(\)\s*\{"
    ),
    ApprovalRule(
        "sql.dml_no_where", "sql_query", TIER_DENY, pred=_is_write_without_where
    ),
    ApprovalRule("sql.ddl", "sql_query", TIER_DENY, pattern=r"^\s*(drop|truncate)\b"),
    ApprovalRule(
        "code.mass_kill",
        "code_interpreter",
        TIER_DENY,
        pattern=r"rm\s+-rf\s+(/|~|\*)(\s|$)",
    ),
    # ── confirm tier ────────────────────────────────────────────────────────
    ApprovalRule(
        "shell.kill_process",
        "shell_interpreter",
        TIER_CONFIRM,
        pattern=r"\b(pkill|kill)\b",
    ),
    ApprovalRule(
        "shell.priv_esc",
        "shell_interpreter",
        TIER_CONFIRM,
        pattern=r"\bsudo\b|chmod\s+777",
    ),
    ApprovalRule("shell.rm_rf", "shell_interpreter", TIER_CONFIRM, pattern=r"rm\s+-rf"),
    ApprovalRule(
        "shell.background_svc", "shell_interpreter", TIER_CONFIRM, pattern=r"\bnohup\b"
    ),
    ApprovalRule(
        "shell.git_force",
        "shell_interpreter",
        TIER_CONFIRM,
        pattern=r"git\s+push\s+\S*\s*--force",
    ),
    ApprovalRule(
        "shell.git_destructive",
        "shell_interpreter",
        TIER_CONFIRM,
        pattern=r"git\s+(reset\s+--hard|clean\s+-fd?)",
    ),
    ApprovalRule(
        "shell.eval_indirect",
        "shell_interpreter",
        TIER_CONFIRM,
        pattern=r"\beval\b|\b(bash|sh|zsh)\s+-c\b",
    ),
    ApprovalRule(
        "shell.killall", "shell_interpreter", TIER_CONFIRM, pattern=r"\bkillall\b"
    ),
    ApprovalRule(
        "shell.composed", "shell_interpreter", TIER_CONFIRM, pred=_is_composed
    ),
    ApprovalRule(
        "code.kill_process",
        "code_interpreter",
        TIER_CONFIRM,
        pattern=r"\bpkill\b|os\.system\(['\"]kill",
    ),
    ApprovalRule("sql.dml_write", "sql_query", TIER_CONFIRM, pred=_is_write_with_where),
    ApprovalRule(
        "web.internal",
        "web_fetch",
        TIER_CONFIRM,
        pattern=r"https?://(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)",
    ),
    # ── auto tier (read-only families) ──────────────────────────────────────
    ApprovalRule(
        "shell.readonly",
        "shell_interpreter",
        TIER_AUTO,
        pred=_is_readonly_pipeline,
    ),
    ApprovalRule(
        "sql.read",
        "sql_query",
        TIER_AUTO,
        pattern=r"^\s*(select|show|desc|describe|explain|with)\b",
    ),
    ApprovalRule("web.public", "web_fetch", TIER_AUTO),
]


class ToolRiskPolicy:
    """Classify a (tool, args) pair into auto / confirm / deny."""

    def __init__(self, rules: Optional[List[ApprovalRule]] = None) -> None:
        self._rules = list(rules if rules is not None else BUILTIN_RULES)

    def classify(self, tool: str, args: dict) -> Tuple[str, str]:
        mode = approval_mode()
        if mode == "off":
            return TIER_AUTO, "mode.off"
        blob = _args_blob(args)
        for rule in sorted(self._rules, key=lambda r: _TIER_RANK[r.tier]):
            if rule.matches(tool, args, blob):
                tier = rule.tier
                if mode == "always" and tier == TIER_AUTO:
                    return TIER_CONFIRM, "mode.always"
                return tier, rule.rule_id
        if mode == "always":
            return TIER_CONFIRM, "mode.always"
        if tool in GATED_TOOLS:
            # Fail safe: unmatched call on a side-effect-capable tool asks.
            return TIER_CONFIRM, "failsafe.gated_tool"
        return TIER_AUTO, "default.readonly"


POLICY = ToolRiskPolicy()


@dataclass
class PendingApproval:
    approval_id: str
    conv_id: str
    tool: str
    args: dict
    rule_id: str
    status: str = "pending"  # pending | approved | rejected | timeout
    scope: str = "once"  # once | session | always
    reason: Optional[str] = None
    created_ts: float = field(default_factory=time.time)
    event: asyncio.Event = field(default_factory=asyncio.Event)
    # "dbgpt" gate waits in-process and pushes approval.resolved itself;
    # "pi" gate returns HTTP 202 and the loopback status poll pushes it.
    engine: str = "dbgpt"
    token: Optional[str] = None  # one-shot redemption token (pi 202 flow)
    finalized: bool = False  # resolved event pushed / pending entry popped
    consumed: bool = False  # redemption token already used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "conv_id": self.conv_id,
            "tool": self.tool,
            "args_preview": preview_args(self.args),
            "rule_id": self.rule_id,
            "status": self.status,
            "scope": self.scope,
            "created_ts": self.created_ts,
        }


def preview_args(args: dict, limit: int = 400) -> str:
    blob = _args_blob(args)
    return blob if len(blob) <= limit else blob[:limit] + " …"


class ApprovalCenter:
    """In-memory registry of pending approvals + scope allowlists."""

    def __init__(self) -> None:
        self._pending: Dict[str, PendingApproval] = {}
        # token -> PendingApproval object (NOT id): the pi status poll pops
        # settled approvals out of ``_pending``, so redemption must hold its
        # own reference or every re-post would 403.
        self._tokens: Dict[str, PendingApproval] = {}
        self._session_allow: Dict[str, set] = {}
        self._always_allow: set = set()

    @staticmethod
    def signature(tool: str, args: dict) -> str:
        blob = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha1(f"{tool}:{blob}".encode("utf-8")).hexdigest()[:12]

    def is_allowed(self, conv_id: str, tool: str, args: dict) -> bool:
        sig = self.signature(tool, args)
        if sig in self._always_allow:
            return True
        return sig in self._session_allow.get(conv_id, set())

    def remember(self, conv_id: str, scope: str, tool: str, args: dict) -> None:
        sig = self.signature(tool, args)
        if scope == "session":
            self._session_allow.setdefault(conv_id, set()).add(sig)
        elif scope == "always":
            self._always_allow.add(sig)

    def register(
        self, conv_id: str, tool: str, args: dict, rule_id: str, engine: str = "dbgpt"
    ) -> PendingApproval:
        pa = PendingApproval(
            approval_id=f"apr_{uuid.uuid4().hex[:10]}",
            conv_id=conv_id,
            tool=tool,
            args=args,
            rule_id=rule_id,
            engine=engine,
        )
        self._pending[pa.approval_id] = pa
        return pa

    def get(self, approval_id: str) -> Optional[PendingApproval]:
        return self._pending.get(approval_id)

    def pop(self, approval_id: str) -> None:
        self._pending.pop(approval_id, None)

    def consume_token(self, token: str) -> Optional[PendingApproval]:
        """Redeem a one-shot token issued when an approval was granted."""
        pa = self._tokens.pop(token, None)
        if pa is None or pa.status != "approved" or pa.consumed:
            return None
        pa.consumed = True
        return pa

    def resolve(
        self,
        approval_id: str,
        decision: str,
        scope: str = "once",
        reason: Optional[str] = None,
    ) -> bool:
        pa = self._pending.get(approval_id)
        if pa is None or pa.status != "pending":
            return False
        pa.status = decision
        pa.scope = scope
        pa.reason = reason
        if decision == "approved":
            self.remember(pa.conv_id, scope, pa.tool, pa.args)
            pa.token = secrets.token_urlsafe(16)
            self._tokens[pa.token] = pa
        pa.event.set()
        return True

    async def wait(self, pa: PendingApproval, ttl: float) -> str:
        try:
            await asyncio.wait_for(pa.event.wait(), timeout=ttl)
        except asyncio.TimeoutError:
            if pa.status == "pending":
                pa.status = "timeout"
        finally:
            self._pending.pop(pa.approval_id, None)
        return pa.status

    def pending_for(self, conv_id: str) -> List[Dict[str, Any]]:
        return [
            pa.to_dict()
            for pa in self._pending.values()
            if pa.conv_id == conv_id and pa.status == "pending"
        ]


approval_center = ApprovalCenter()

StreamCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]

def deny_observation(tool: str, rule_id: str) -> str:
    return (
        f"[policy] {tool} was blocked by safety policy (rule: {rule_id}). "
        "Do not retry the same operation; switch to a read-only or "
        "lower-risk alternative, or explain to the user why it is not "
        "possible."
    )


def reject_observation(tool: str, decision: str, reason: Optional[str]) -> str:
    why = reason or (
        "confirmation timed out" if decision == "timeout" else "no reason given"
    )
    return (
        f"[approval] The user rejected this {tool} call (reason: {why}). "
        "Do not retry the same operation; if the goal still needs to be "
        "achieved, switch to a read-only or lower-risk approach and explain "
        "to the user."
    )


def make_approval_gate(
    conv_id: str,
    stream_callback: StreamCallback,
    center: Optional[ApprovalCenter] = None,
    policy: Optional[ToolRiskPolicy] = None,
):
    """Build the tool_action gate closure for one conversation round."""
    center = center or approval_center
    policy = policy or POLICY

    async def gate(name: str, args: dict) -> Optional[str]:
        mode = approval_mode()
        if mode == "off":
            return None
        if mode != "always" and center.is_allowed(conv_id, name, args):
            return None
        tier, rule_id = policy.classify(name, args)
        if tier == TIER_AUTO:
            return None
        if tier == TIER_DENY:
            return deny_observation(name, rule_id)

        pa = center.register(conv_id, name, args, rule_id)
        await stream_callback(
            "approval.requested",
            {
                "approval_id": pa.approval_id,
                "conv_id": conv_id,
                "tool": name,
                "args_preview": preview_args(args),
                "rule_id": rule_id,
                "risk": tier,
                "ttl_seconds": int(approval_ttl_seconds()),
                "ts": pa.created_ts,
            },
        )
        logger.info(
            "approval gate: waiting for user decision, approval_id=%s tool=%s",
            pa.approval_id,
            name,
        )
        decision = await center.wait(pa, approval_ttl_seconds())
        await stream_callback(
            "approval.resolved",
            {
                "approval_id": pa.approval_id,
                "conv_id": conv_id,
                "decision": decision,
                "scope": pa.scope,
            },
        )
        if decision == "approved":
            return None
        return reject_observation(name, decision, pa.reason)

    return gate
