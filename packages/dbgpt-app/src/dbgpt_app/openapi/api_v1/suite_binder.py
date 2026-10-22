"""Suite binder (T3): resolve the scenario-suite pin of a turn and build a binding.

Resolution order (mirrors the ``ext_info.harness_engine`` convention):

1. explicit per-request ``ext_info.suite`` (``slug`` or ``slug@version``);
2. the conversation's sticky pin = latest ``pin``/``switch`` event for conv_uid;
3. no suite (behaviour unchanged).

The binding carries: SOP text (read from the package on disk), canonicalized
tool allow/deny sets, artifacts and the semantic-layer binding.  When the
semantic layer is unavailable the binding **degrades with a watermark** instead
of raising (design §7.2: 降级的只是口径保证，不是安全边界).

Enforcement: :func:`make_suite_gate` composes OUTSIDE the approval gate on the
dbgpt engine; the pi engine consults :func:`get_conv_suite` in its loopback
tool-run endpoint.  Suite rules can only block tools, never widen approvals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set

from dbgpt._private.config import Config

logger = logging.getLogger(__name__)

#: Module-level singleton handle (``Config()`` is the ``dbgpt._private.config``
#: singleton); mirrors the pattern used by agentic_data_api / harness_pi_stream.
CFG = Config()

#: Suite manifest tool names that map onto differently-named registered tools.
SUITE_TOOL_ALIASES = {
    "sql_execute": "sql_query",
    "shell": "bash",
    "shell_interpreter": "bash",
    "code_interpreter": "code",
}

#: Conversational + loop-control utilities every suite keeps, even under a
#: strict allowlist.  ``terminate`` is the ReAct loop's end-of-turn tool:
#: blocking it would leave the agent unable to finish, so it is always allowed.
IMPLICIT_ALLOW = {"question", "todowrite", "terminate"}

SEMANTIC_DEGRADED_WATERMARK = (
    "⚠️ 语义层未就绪：本次基于表摘要/原始 schema 取数（水位线：无指标口径 / "
    "默认过滤 / 样例保证，结果需人工复核）。只读、超时、行数与行级权限护栏照常落地。"
)


def canonical_suite_tool(name: str) -> str:
    """Normalize a manifest tool name to the registered tool name."""
    from dbgpt_app.openapi.api_v1.tool_names import canonical_tool

    base = canonical_tool(name)
    return SUITE_TOOL_ALIASES.get(base, base)


@dataclass
class SuiteBinding:
    """A resolved suite, bound to one conversation turn."""

    name: str
    version: str
    sop_text: str = ""
    allow: Optional[Set[str]] = None  # None = unrestricted
    deny: Set[str] = field(default_factory=set)
    artifacts: list = field(default_factory=list)
    semantic: Dict[str, Any] = field(default_factory=dict)
    semantic_status: str = "degraded"  # bound | degraded
    watermark: str = ""

    def violation(self, tool_name: str) -> Optional[str]:
        """Return a blocking observation when the tool breaks suite rules."""
        if tool_name in self.deny:
            return (
                f"[suite guardrail] tool `{tool_name}` is denied by suite "
                f"{self.name}@{self.version} (tools.deny). This operation is "
                "outside the current scenario boundary; finish the task with "
                "in-suite capabilities or tell the user to switch suites."
            )
        if (
            self.allow is not None
            and tool_name not in self.allow
            and tool_name not in IMPLICIT_ALLOW
        ):
            return (
                f"[suite guardrail] tool `{tool_name}` is not in suite "
                f"{self.name}@{self.version} allowlist (tools.allow). Only "
                "whitelisted tools may run in this scenario."
            )
        return None


# ---------------------------------------------------------------------------
# pi-engine per-conversation binding registry (pi runs in a separate process,
# so a contextvar cannot cross the loopback HTTP call; mirror tool_bridge).
_CONV_SUITE: Dict[str, SuiteBinding] = {}


def set_conv_suite(conv_id: str, binding: Optional[SuiteBinding]) -> None:
    if binding is None:
        _CONV_SUITE.pop(conv_id, None)
    else:
        _CONV_SUITE[conv_id] = binding


def get_conv_suite(conv_id: str) -> Optional[SuiteBinding]:
    return _CONV_SUITE.get(conv_id)


def clear_conv_suite(conv_id: str) -> None:
    _CONV_SUITE.pop(conv_id, None)


# ---------------------------------------------------------------------------
def _plugins_service():
    from dbgpt_serve.plugins.config import SERVE_SERVICE_COMPONENT_NAME
    from dbgpt_serve.plugins.service.service import Service

    return CFG.SYSTEM_APP.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


def resolve_suite_ref(ext_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """Explicit per-request pin: ``ext_info.suite`` = slug or slug@version."""
    if not isinstance(ext_info, dict):
        return None
    raw = str(ext_info.get("suite") or "").strip()
    if not raw:
        return None
    return raw.split("@", 1)[0]


def _read_sop(package_path: Optional[str], manifest: Dict[str, Any]) -> str:
    rel = manifest.get("sop")
    if not package_path or not rel:
        return ""
    sop_file = Path(package_path) / str(rel)
    try:
        return sop_file.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 - fail-soft: missing sop must not block turns
        logger.warning("suite sop unreadable: %s", sop_file)
        return ""


def load_binding(slug: str) -> Optional[SuiteBinding]:
    """Build a binding from the registry row + the package on disk."""
    try:
        service = _plugins_service()
    except Exception:  # noqa: BLE001 - plugins serve not registered
        logger.debug("plugins service unavailable", exc_info=True)
        return None
    row = service.get(slug)
    if row is None or row.status != "enabled":
        return None
    snapshot = row.manifest_snapshot or {}
    from dbgpt_serve.plugins.loader import load_suite_dir

    pkg = load_suite_dir(Path(row.package_path)) if row.package_path else None
    manifest = pkg.manifest if pkg else {}
    sop_text = _read_sop(row.package_path, manifest)
    tools = snapshot.get("tools") or {}
    allow_raw = tools.get("allow") or []
    deny_raw = tools.get("deny") or []
    allow: Optional[Set[str]] = (
        {canonical_suite_tool(t) for t in allow_raw} if allow_raw else None
    )
    deny = {canonical_suite_tool(t) for t in deny_raw}
    semantic = snapshot.get("semantic") or {}
    binding = SuiteBinding(
        name=row.name,
        version=row.version,
        sop_text=sop_text,
        allow=allow,
        deny=deny,
        artifacts=snapshot.get("artifacts") or [],
        semantic=semantic,
    )
    binding.semantic_status = _probe_semantic_status(semantic)
    if binding.semantic_status == "degraded":
        binding.watermark = SEMANTIC_DEGRADED_WATERMARK
    return binding


def _probe_semantic_status(semantic: Dict[str, Any]) -> str:
    """Semantic layer is not implemented in-code yet: always degrade (P0)."""
    if not semantic:
        return "degraded"
    try:  # pragma: no cover - semantic serve module lands later
        import dbgpt_serve.semantic  # noqa: F401

        return "bound"
    except Exception:  # noqa: BLE001
        return "degraded"


def resolve_binding_for_turn(dialogue: Any) -> Optional[SuiteBinding]:
    """Resolve + record the suite pin for one chat turn (fail-soft)."""
    try:
        ext_info = getattr(dialogue, "ext_info", None)
        conv_uid = getattr(dialogue, "conv_uid", None) or ""
        ref = resolve_suite_ref(ext_info)
        service = _plugins_service()
        if ref is None and conv_uid:
            pin = service.registry.current_pin(conv_uid)
            ref = pin[0] if pin else None
        if ref is None:
            return None
        binding = load_binding(ref)
        if binding is None:
            logger.info("suite pin %s not enabled/installed; turn runs unbound", ref)
            return None
        if conv_uid:
            prev = service.registry.current_pin(conv_uid)
            if prev is None:
                service.registry.record_pin(conv_uid, binding.name, binding.version)
            elif (prev[0], prev[1]) != (binding.name, binding.version):
                service.registry.record_switch(
                    conv_uid, prev[0], prev[1], binding.name, binding.version
                )
        logger.info(
            "suite bound: %s@%s allow=%s deny=%s semantic=%s",
            binding.name,
            binding.version,
            sorted(binding.allow) if binding.allow else None,
            sorted(binding.deny),
            binding.semantic_status,
        )
        return binding
    except Exception:  # noqa: BLE001 - binding must never break a chat turn
        logger.warning("suite binding failed; turn runs unbound", exc_info=True)
        return None


def build_sop_block(binding: SuiteBinding) -> str:
    """SOP section prepended to the system prompt (dbgpt) / turn prompt (pi)."""
    header = (
        f"\n\n## 场景套件 SOP（{binding.name}@{binding.version}）\n"
        "以下是本套件的行事规程，优先于你的通用习惯；与用户请求冲突时先说明边界：\n"
    )
    body = binding.sop_text.strip() or "（本套件未携带 sop 文件）"
    watermark = f"\n\n> {binding.watermark}" if binding.watermark else ""
    return header + body + watermark


def make_suite_gate(binding: SuiteBinding):
    """Async gate fn with the same signature as the approval gate."""

    async def gate(name: str, args: dict) -> Optional[str]:  # noqa: ARG001
        return binding.violation(name)

    return gate


def compose_gates(suite_gate, inner_gate):
    """Suite rules are checked BEFORE the approval gate (deny wins early)."""

    async def composed(name: str, args: dict):
        observation = await suite_gate(name, args)
        if observation is not None:
            return observation
        return await inner_gate(name, args)

    return composed
