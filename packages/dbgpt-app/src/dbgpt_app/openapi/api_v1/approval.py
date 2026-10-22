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

from .approval_code_risk import code_has_sink, code_provably_safe
from .tool_names import canonical_tool

logger = logging.getLogger(__name__)

TIER_AUTO = "auto"
TIER_CONFIRM = "confirm"
TIER_DENY = "deny"
_TIER_RANK = {TIER_DENY: 0, TIER_CONFIRM: 1, TIER_AUTO: 2}

# Tools whose unmatched calls fail safe to ``confirm`` instead of ``auto``.
GATED_TOOLS = {"bash", "code", "sql_query", "web_fetch"}

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
    """Global mode: ``off`` | ``tiered`` (default) | ``always``.

    L2 setting row wins over the env var (design §4.4).
    """
    from dbgpt_app.openapi.api_v1 import approval_policy

    value = approval_policy.get_setting("mode") or os.environ.get(
        "DBGPT_APPROVAL_MODE", "tiered"
    )
    return str(value).strip().lower()


def approval_ttl_seconds() -> float:
    from dbgpt_app.openapi.api_v1 import approval_policy

    value = approval_policy.get_setting("ttl_seconds") or os.environ.get(
        "DBGPT_APPROVAL_TTL_SECONDS", "300"
    )
    try:
        return float(value)
    except (TypeError, ValueError):
        return 300.0


def approval_intent_enabled() -> bool:
    from dbgpt_app.openapi.api_v1 import approval_policy

    return approval_policy.get_setting("intent_analysis", "true") != "false"


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
    r"date|whoami|id|uname|hostname|jq|tree|stat|file|cut|tr|uniq|diff|comm|"
    r"paste|column|nl|md5|shasum|sha256sum|basename|dirname|readlink|"
    r"realpath|seq|bc|awk|sed|sort|tar|lsof|netstat)\b",
    re.IGNORECASE,
)
_COMPOSE_RE = re.compile(r"[|;&]+|\$\(|`")
_ENV_PREFIX_RE = re.compile(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")
# Output redirection writes a file, so the command is never read-only no
# matter how pure the left side looks (``ls > out.txt``).
_REDIRECT_RE = re.compile(r">")
# Flags that turn an otherwise read-only verb into a writer / executor.
_FLAG_GUARDS = (
    (
        re.compile(r"^find\b", re.IGNORECASE),
        re.compile(r"-delete|-exec(dir)?\b|-ok(dir)?\b"),
    ),
    (re.compile(r"^sort\b", re.IGNORECASE), re.compile(r"\s-o\s|--output")),
    (re.compile(r"^sed\b", re.IGNORECASE), re.compile(r"\s-i\b|--in-place")),
    (re.compile(r"^awk\b", re.IGNORECASE), re.compile(r"system\s*\(")),
)


def _command_segments(blob: str) -> List[str]:
    return [s for s in _COMPOSE_RE.split(blob) if s and s.strip()]


def _segment_readonly(seg: str) -> bool:
    seg = _ENV_PREFIX_RE.sub("", seg.strip())
    if not _READONLY_CMD_RE.match(seg):
        return False
    # tar is read-only only when listing; create/extract write files.
    if re.match(r"tar\b", seg, re.IGNORECASE) and not re.search(
        r"(^|\s)-[a-z]*t[a-z]*\b|--list\b", seg
    ):
        return False
    for head, bad in _FLAG_GUARDS:
        if head.match(seg) and bad.search(seg):
            return False
    return True


def _is_readonly_pipeline(args: dict) -> bool:
    blob = _args_blob(args)
    if not blob.strip():
        return False
    if _REDIRECT_RE.search(blob):
        return False
    segments = _command_segments(blob)
    return bool(segments) and all(_segment_readonly(seg) for seg in segments)


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
        rule_tool = canonical_tool(self.tool)
        if rule_tool != "*" and rule_tool != canonical_tool(tool):
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
        "bash",
        TIER_DENY,
        pattern=r"rm\s+-rf\s+(/|~|\*)(\s|$)",
    ),
    ApprovalRule(
        "shell.pipe_exec",
        "bash",
        TIER_DENY,
        pattern=r"(curl|wget)[^\n]*\|\s*(sh|bash|zsh)",
    ),
    ApprovalRule("shell.mkfs", "bash", TIER_DENY, pattern=r"\bmkfs\b"),
    ApprovalRule(
        "shell.dd_device",
        "bash",
        TIER_DENY,
        pattern=r"\bdd\b[^\n]*of=/dev/",
    ),
    ApprovalRule(
        "shell.chmod_root",
        "bash",
        TIER_DENY,
        pattern=r"chmod\s+(-R\s+)?777\s+(/|~)(\s|$)",
    ),
    ApprovalRule(
        "shell.fork_bomb", "bash", TIER_DENY, pattern=r":\(\)\s*\{"
    ),
    ApprovalRule(
        "sql.dml_no_where", "sql_query", TIER_DENY, pred=_is_write_without_where
    ),
    ApprovalRule("sql.ddl", "sql_query", TIER_DENY, pattern=r"^\s*(drop|truncate)\b"),
    ApprovalRule(
        "code.mass_kill",
        "code",
        TIER_DENY,
        pattern=r"rm\s+-rf\s+(/|~|\*)(\s|$)",
    ),
    # ── confirm tier ────────────────────────────────────────────────────────
    ApprovalRule(
        "shell.kill_process",
        "bash",
        TIER_CONFIRM,
        pattern=r"\b(pkill|kill)\b",
    ),
    ApprovalRule(
        "shell.priv_esc",
        "bash",
        TIER_CONFIRM,
        pattern=r"\bsudo\b|chmod\s+777",
    ),
    ApprovalRule("shell.rm_rf", "bash", TIER_CONFIRM, pattern=r"rm\s+-rf"),
    ApprovalRule(
        "shell.background_svc", "bash", TIER_CONFIRM, pattern=r"\bnohup\b"
    ),
    ApprovalRule(
        "shell.git_force",
        "bash",
        TIER_CONFIRM,
        pattern=r"git\s+push\s+\S*\s*--force",
    ),
    ApprovalRule(
        "shell.git_destructive",
        "bash",
        TIER_CONFIRM,
        pattern=r"git\s+(reset\s+--hard|clean\s+-fd?)",
    ),
    ApprovalRule(
        "shell.eval_indirect",
        "bash",
        TIER_CONFIRM,
        pattern=r"\beval\b|\b(bash|sh|zsh)\s+-c\b",
    ),
    ApprovalRule(
        "shell.killall", "bash", TIER_CONFIRM, pattern=r"\bkillall\b"
    ),
    ApprovalRule(
        "shell.composed", "bash", TIER_CONFIRM, pred=_is_composed
    ),
    ApprovalRule(
        "code.kill_process",
        "code",
        TIER_CONFIRM,
        pattern=r"\bpkill\b|os\.system\(['\"]kill",
    ),
    ApprovalRule(
        "code.static_sink",
        "code",
        TIER_CONFIRM,
        pred=code_has_sink,
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
        "bash",
        TIER_AUTO,
        pred=_is_readonly_pipeline,
    ),
    ApprovalRule(
        "code.static_auto",
        "code",
        TIER_AUTO,
        pred=code_provably_safe,
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
    """Classify a (tool, args) pair into auto / confirm / deny.

    Evaluation order (design §4): L2 setting rules (DB) are listed before the
    builtin table and win ties within a tier; deny matches can never be
    relaxed by a per-tool override; overrides then beat confirm/auto matches.
    """

    def __init__(self, rules: Optional[List[ApprovalRule]] = None) -> None:
        self._rules = list(rules if rules is not None else BUILTIN_RULES)

    def _merged_rules(self) -> List[ApprovalRule]:
        from dbgpt_app.openapi.api_v1 import approval_policy

        dyn = [
            ApprovalRule(
                rule_id=f"setting:{r['id']}",
                tool=r["tool"],
                tier=r["tier"],
                pattern=r["arg_pattern"],
                source="setting",
            )
            for r in approval_policy.dynamic_rules()
        ]
        return dyn + self._rules

    def classify(self, tool: str, args: dict) -> Tuple[str, str]:
        verdict, _ = self._classify(tool, args)
        return verdict

    def classify_trace(
        self, tool: str, args: dict
    ) -> Tuple[Tuple[str, str], List[Dict[str, Any]]]:
        """Classify with a per-rule evaluation trace (setting playground)."""
        return self._classify(tool, args)

    def _classify(
        self, tool: str, args: dict
    ) -> Tuple[Tuple[str, str], List[Dict[str, Any]]]:
        trace: List[Dict[str, Any]] = []
        tool = canonical_tool(tool)
        mode = approval_mode()
        if mode == "off":
            trace.append({"rule_id": "mode.off", "tier": TIER_AUTO, "hit": True})
            return (TIER_AUTO, "mode.off"), trace
        blob = _args_blob(args)
        hit: Optional[Tuple[str, str]] = None
        for rule in sorted(self._merged_rules(), key=lambda r: _TIER_RANK[r.tier]):
            matched = rule.matches(tool, args, blob)
            trace.append({"rule_id": rule.rule_id, "tier": rule.tier, "hit": matched})
            if matched and hit is None:
                hit = (rule.tier, rule.rule_id)
        if hit and hit[0] == TIER_DENY:
            return hit, trace
        from dbgpt_app.openapi.api_v1 import approval_policy

        forced = approval_policy.tool_override(tool)
        if forced:
            trace.append(
                {"rule_id": "setting.override", "tier": forced, "hit": True}
            )
            return (forced, "setting.override"), trace
        if hit:
            if mode == "always" and hit[0] == TIER_AUTO:
                return (TIER_CONFIRM, "mode.always"), trace
            return hit, trace
        if mode == "always":
            return (TIER_CONFIRM, "mode.always"), trace
        if tool in GATED_TOOLS:
            # Fail safe: unmatched call on a side-effect-capable tool asks
            # (relaxable to auto via the setting page fail_safe param).
            from dbgpt_app.openapi.api_v1 import approval_policy

            fail_safe = approval_policy.get_setting("fail_safe", "confirm")
            tier = TIER_AUTO if fail_safe == "auto" else TIER_CONFIRM
            return (tier, "failsafe.gated_tool"), trace
        return (TIER_AUTO, "default.readonly"), trace


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

    @staticmethod
    def memory_key(tool: str, args: dict) -> str:
        """Coarse "class of call" key for session/always memory.

        The exact-args hash was too narrow: approving ``pkill -f x`` with
        scope=always still popped the card for ``pkill -f y``. Key by command
        head / SQL verb / URL host so the scope dropdown keeps its promise.
        """
        blob = _args_blob(args)
        if tool == "shell_interpreter":
            head = blob.strip().split(None, 1)[:1]
            name_ = os.path.basename(head[0]) if head else blob.strip()[:24]
            return f"{tool}: {name_}*"
        if tool == "code_interpreter":
            # Code is Turing-complete: the first token (import/def/for…)
            # carries no safety meaning, so memory stays exact-script only.
            return f"{tool}: {ApprovalCenter.signature(tool, args)}"
        if tool == "sql_query":
            verb = re.match(r"\s*([a-zA-Z]+)", blob)
            return f"{tool}: {(verb.group(1).upper() if verb else 'OTHER')} …"
        if tool == "web_fetch":
            host = re.match(r"\s*https?://([^/:\s]+)", blob)
            return f"{tool}: {(host.group(1) if host else blob.strip()[:24])}/*"
        return f"{tool}: {ApprovalCenter.signature(tool, args)}"

    def is_allowed(self, conv_id: str, tool: str, args: dict) -> bool:
        key = self.memory_key(tool, args)
        sig = self.signature(tool, args)
        for cand in (key, sig):
            if cand in self._always_allow:
                return True
            if cand in self._session_allow.get(conv_id, set()):
                return True
        return False

    def remember(self, conv_id: str, scope: str, tool: str, args: dict) -> None:
        key = self.memory_key(tool, args)
        if scope == "session":
            self._session_allow.setdefault(conv_id, set()).add(key)
        elif scope == "always":
            self._always_allow.add(key)

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
        from dbgpt_app.openapi.api_v1 import approval_audit as audit

        audit.audit_register(
            pa.approval_id,
            conv_id,
            engine,
            tool,
            self.signature(tool, args),
            preview_args(args),
            rule_id,
            TIER_CONFIRM,
        )
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
        actor: Optional[str] = None,
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
        from dbgpt_app.openapi.api_v1 import approval_audit as audit

        audit.audit_decision(
            approval_id, decision, scope, reason, actor, settle_source="rest"
        )
        pa.event.set()
        return True

    async def wait(self, pa: PendingApproval, ttl: float) -> str:
        try:
            await asyncio.wait_for(pa.event.wait(), timeout=ttl)
        except asyncio.TimeoutError:
            if pa.status == "pending":
                pa.status = "timeout"
                from dbgpt_app.openapi.api_v1 import approval_audit as audit

                audit.audit_decision(
                    pa.approval_id,
                    "timeout",
                    None,
                    None,
                    None,
                    settle_source="ttl",
                )
        finally:
            self._pending.pop(pa.approval_id, None)
        return pa.status

    def pending_for(self, conv_id: str) -> List[Dict[str, Any]]:
        return [
            pa.to_dict()
            for pa in self._pending.values()
            if pa.conv_id == conv_id and pa.status == "pending"
        ]

    def revoke(
        self, scope: str, signature: str, conv_id: Optional[str] = None
    ) -> bool:
        """Drop one whitelist memory entry (setting page management)."""
        if scope == "always":
            if signature in self._always_allow:
                self._always_allow.discard(signature)
                return True
            return False
        if scope == "session" and conv_id:
            sigs = self._session_allow.get(conv_id, set())
            if signature in sigs:
                sigs.discard(signature)
                return True
        return False


approval_center = ApprovalCenter()

StreamCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]

# ── Intent analysis (approval.intent) ───────────────────────────────────────
# Async, never blocks the card: the dock shows a spinner (Allow disabled,
# Reject enabled) until ``approval.intent`` arrives; on analyzer failure a
# fallback bullet is pushed so Allow is never held hostage.
INTENT_MODEL_ENV = "DBGPT_APPROVAL_INTENT_MODEL"
INTENT_TIMEOUT_SECONDS = 10.0
INTENT_FALLBACK_BULLETS = [
    "Intent analysis unavailable — review the command content and its blast "
    "radius yourself before deciding."
]
INTENT_FALLBACK_BULLETS_ZH = ["意图分析不可用，请自行核对命令内容与影响范围后决策。"]

IntentAnalyzer = Callable[[str, dict], Awaitable[Optional[List[str]]]]

_INTENT_PROMPT = (
    "You are a command-intent analyzer. For the tool call below, output 3-5 "
    "bullet points in English explaining what it will do, its blast radius "
    "and its consequences, so the user can decide whether to approve. "
    "Requirements:\n"
    "- one sentence per bullet, in execution order;\n"
    "- wrap impact/risk words (e.g. force-kill, abort immediately, "
    "irreversible, delete, overwrite, exfiltrate, restart in background) in "
    "a pair of ** for emphasis;\n"
    "- output ONLY a JSON array of strings, nothing else.\n"
    "tool: {tool}\nargs: {args}"
)

_INTENT_PROMPT_ZH = (
    "你是命令意图分析器。针对下面这次工具调用，用中文输出 3-5 条要点，"
    "说明它会做什么、影响范围与后果，供用户审批决策。要求：\n"
    "- 每条一句话，按执行顺序；\n"
    "- 把影响/风险词（如强制终止、立即中断、不可恢复、删除、覆盖、外发、"
    "后台重启等）用一对 ** 包裹强调；\n"
    "- 只输出 JSON 字符串数组，不要任何其他内容。\n"
    "工具：{tool}\n参数：{args}"
)

# ── Per-conversation UI locale ──────────────────────────────────────────────
# The intent bullets are rendered verbatim in the approval dock, so they must
# follow the *UI* language. The frontend sends its i18n locale with every chat
# request (``ext_info.locale``); both engines record it here at turn start and
# the intent path reads it back by conv_id.
DEFAULT_INTENT_LOCALE = "en"
_CONV_LOCALE: Dict[str, str] = {}
_CONV_LOCALE_MAX = 512


def normalize_intent_locale(locale: Optional[str]) -> str:
    """Map any locale tag (``zh-CN``, ``en_US``, …) onto ``zh``/``en``."""
    tag = (locale or "").strip().lower().replace("_", "-")
    if tag.startswith("zh"):
        return "zh"
    if tag.startswith("en"):
        return "en"
    return DEFAULT_INTENT_LOCALE


def locale_from_ext_info(ext_info: Optional[dict]) -> str:
    ext = ext_info if isinstance(ext_info, dict) else {}
    return normalize_intent_locale(
        ext.get("locale") or ext.get("lang") or ext.get("language")
    )


def set_conv_locale(conv_id: Optional[str], locale: Optional[str]) -> None:
    """Record the UI locale for one conversation (bounded, turn-start)."""
    if not conv_id:
        return
    _CONV_LOCALE[conv_id] = normalize_intent_locale(locale)
    while len(_CONV_LOCALE) > _CONV_LOCALE_MAX:
        _CONV_LOCALE.pop(next(iter(_CONV_LOCALE)))


def get_conv_locale(conv_id: Optional[str]) -> str:
    return _CONV_LOCALE.get(conv_id or "", DEFAULT_INTENT_LOCALE)


def intent_prompt(lang: str) -> str:
    return _INTENT_PROMPT_ZH if lang == "zh" else _INTENT_PROMPT


def intent_fallback_bullets(lang: str) -> List[str]:
    return list(INTENT_FALLBACK_BULLETS_ZH if lang == "zh" else INTENT_FALLBACK_BULLETS)


def parse_intent_bullets(text: str) -> List[str]:
    """Extract <=6 bullets from LLM output (JSON array or line list)."""
    text = (text or "").strip()
    if not text:
        return []
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                bullets = [str(x).strip() for x in data if str(x).strip()]
                if bullets:
                    return bullets[:6]
        except Exception:
            pass
    bullets = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*").strip()
        numbered = re.match(r"^\d+[.)]\s*(.*)$", line)
        if numbered:
            line = numbered.group(1).strip()
        if line:
            bullets.append(line[:160])
        if len(bullets) >= 6:
            break
    return bullets


def make_intent_analyzer(
    llm_client: Any,
    model_name: Optional[str] = None,
    lang: Optional[str] = None,
) -> IntentAnalyzer:
    """Build an analyzer bound to an LLM client; env model wins over round.

    ``lang`` pins the bullet language (``zh``/``en``); without it the
    analyzer emits the default locale, so callers that know the
    conversation's UI locale should pass it explicitly.
    """
    pinned = normalize_intent_locale(lang) if lang else None

    async def analyze(tool: str, args: dict) -> Optional[List[str]]:
        target = os.environ.get(INTENT_MODEL_ENV) or model_name
        if llm_client is None or not target:
            return None
        from dbgpt.core.interface.llm import ModelMessage, ModelRequest

        prompt = intent_prompt(pinned or DEFAULT_INTENT_LOCALE)
        request = ModelRequest(
            model=target,
            messages=[
                ModelMessage(
                    role="system",
                    content=prompt.format(tool=tool, args=preview_args(args, 1200)),
                )
            ],
        )
        output = await asyncio.wait_for(
            llm_client.generate(request), timeout=INTENT_TIMEOUT_SECONDS
        )
        text = getattr(output, "text", None) or str(output)
        return parse_intent_bullets(text) or None

    return analyze


_INTENT_CACHE: Dict[str, Any] = {}


def get_intent_analyzer(
    model_name: Optional[str] = None, lang: Optional[str] = None
) -> Optional[IntentAnalyzer]:
    """Process-wide analyzer for paths without a round LLM client (pi)."""
    locale = normalize_intent_locale(lang) if lang else None
    cache_key = f"{model_name or '__default__'}::{locale or '__conv__'}"
    if cache_key in _INTENT_CACHE:
        return _INTENT_CACHE[cache_key]
    analyzer: Optional[IntentAnalyzer] = None
    try:
        from dbgpt._private.config import Config
        from dbgpt.component import ComponentType
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.client import DefaultLLMClient

        client = DefaultLLMClient(
            Config()
            .SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            )
            .create(),
            auto_convert_message=True,
        )
        analyzer = make_intent_analyzer(client, model_name, lang=locale)
    except Exception:
        logger.exception("approval intent analyzer unavailable")
    _INTENT_CACHE[cache_key] = analyzer
    return analyzer


async def push_intent(
    pa: PendingApproval,
    stream_callback: StreamCallback,
    analyzer: Optional[IntentAnalyzer],
) -> None:
    bullets: Optional[List[str]] = None
    if analyzer is not None:
        try:
            bullets = await analyzer(pa.tool, pa.args)
        except Exception:
            logger.exception(
                "approval intent analysis failed, approval_id=%s", pa.approval_id
            )
    if not bullets:
        # Fallback follows the conversation's UI locale so the dock never
        # shows a language the user did not choose.
        bullets = intent_fallback_bullets(get_conv_locale(pa.conv_id))
    from dbgpt_app.openapi.api_v1 import approval_audit as audit

    audit.audit_intent(pa.approval_id, json.dumps(bullets, ensure_ascii=False))
    await stream_callback(
        "approval.intent",
        {"approval_id": pa.approval_id, "conv_id": pa.conv_id, "bullets": bullets},
    )


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
    intent_analyzer: Optional["IntentAnalyzer"] = None,
):
    """Build the tool_action gate closure for one conversation round."""
    center = center or approval_center
    policy = policy or POLICY

    async def gate(name: str, args: dict) -> Optional[str]:
        mode = approval_mode()
        if mode == "off":
            return None
        # Deny is evaluated BEFORE whitelist memory: a remembered class key
        # (e.g. ``rm tmp/x`` -> "rm*") must never shield a deny-tier call
        # (``rm -rf /``) that shares the same command head.
        tier, rule_id = policy.classify(name, args)
        if tier == TIER_DENY:
            return deny_observation(name, rule_id)
        if mode != "always" and center.is_allowed(conv_id, name, args):
            return None
        if tier == TIER_AUTO:
            return None

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
                "memory_key": center.memory_key(name, args),
                "ttl_seconds": int(approval_ttl_seconds()),
                "ts": pa.created_ts,
            },
        )
        logger.info(
            "approval gate: waiting for user decision, approval_id=%s tool=%s",
            pa.approval_id,
            name,
        )
        # Always push an intent frame (real bullets, or the fallback when
        # analysis is off / the analyzer is unavailable): the dock disables
        # Allow until the frame arrives, so skipping the push would stall
        # the round until the approval TTL expires.
        asyncio.ensure_future(push_intent(pa, stream_callback, intent_analyzer))
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
