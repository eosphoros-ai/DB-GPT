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

import hashlib
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Set
from urllib.parse import unquote, urlsplit

from dbgpt._private.config import Config

logger = logging.getLogger(__name__)

#: Module-level singleton handle (``Config()`` is the ``dbgpt._private.config``
#: singleton); mirrors the pattern used by agentic_data_api / harness_pi_stream.
CFG = Config()

#: Suite manifest tool names that map onto differently-named registered tools.
SUITE_TOOL_ALIASES = {
    "sql_execute": "sql_query",
    "chart": "chart_query",
    "report_export": "generate_report",
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

_REPORT_AGENT_SCOPE: ContextVar[bool] = ContextVar("suite_report_agent", default=False)
_REPORT_AGENT_TOOLS = frozenset(
    {
        "html_interpreter",
        "report_evidence_manifest",
        "read_file",
        "request_report_calculation",
        "append_report_sections",
    }
)


@contextmanager
def report_agent_tool_scope() -> Iterator[None]:
    """Delegate rendering helpers only while the dedicated report child runs."""
    token = _REPORT_AGENT_SCOPE.set(True)
    try:
        yield
    finally:
        _REPORT_AGENT_SCOPE.reset(token)


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
    package_path: str = ""
    commands: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    command: str = ""
    command_description: str = ""
    command_skill: str = ""
    command_skill_text: str = ""
    command_error: str = ""
    package_format: str = "scenario-suite"
    loaded_documents: list = field(default_factory=list)

    def violation(self, tool_name: str) -> Optional[str]:
        """Return a blocking observation when the tool breaks suite rules."""
        if self.command_error and tool_name not in IMPLICIT_ALLOW:
            return f"[suite command] {self.command_error}"
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
        package_path=row.package_path or "",
        commands=manifest.get("commands") or [],
        skills=manifest.get("skills") or [],
        package_format=manifest.get("package_format", "scenario-suite"),
    )
    binding.semantic_status = _probe_semantic_status(semantic)
    if binding.semantic_status == "degraded" and (
        binding.package_format != "qwenwork-plugin" or binding.semantic
    ):
        binding.watermark = SEMANTIC_DEGRADED_WATERMARK
    return binding


def bind_command(binding: SuiteBinding, command_name: str) -> None:
    """Resolve a command and its declared skill inside the installed package."""
    binding.command = command_name
    binding.command_error = ""
    binding.command_description = ""
    binding.command_skill = ""
    binding.command_skill_text = ""
    binding.loaded_documents = []
    command = next(
        (
            cmd
            for cmd in binding.commands
            if isinstance(cmd, dict)
            and (
                cmd.get("name") == command_name
                or command_name in cmd.get("aliases", [])
            )
        ),
        None,
    )
    if command is None:
        binding.command_error = f"套件 {binding.name} 没有快捷命令 {command_name}"
        return
    binding.command = command["name"]
    binding.command_description = (
        command.get("description") or command.get("summary") or ""
    )
    skill_name = command.get("skill")
    if not skill_name:
        binding.command_error = f"快捷命令 {command_name} 未声明对应技能"
        return
    skill = next(
        (
            item
            for item in binding.skills
            if isinstance(item, dict) and item.get("name") == skill_name
        ),
        None,
    )
    binding.command_skill = str(skill_name)
    try:
        if not skill or not skill.get("path") or not binding.package_path:
            raise ValueError("技能未在套件清单中声明路径")
        root = Path(binding.package_path).resolve()
        skill_file = (root / skill["path"]).resolve()
        if not skill_file.is_relative_to(root):
            raise ValueError("技能路径不在套件目录内")
        binding.command_skill_text = skill_file.read_text(encoding="utf-8").strip()
        if not binding.command_skill_text:
            raise ValueError("技能内容为空")
        if len(binding.command_skill_text.encode("utf-8")) > 512 * 1024:
            raise ValueError("套件技能与引用正文超过 512KB")
        binding.loaded_documents = [
            {
                "path": skill_file.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(
                    binding.command_skill_text.encode("utf-8")
                ).hexdigest(),
                "status": "loaded",
            }
        ]
        # Native plugins reference shared knowledge and templates directly in
        # their SKILL.md. Resolve those links within the installed package,
        # never through the agent's unrestricted filesystem tools.
        if binding.package_format == "qwenwork-plugin":
            binding.loaded_documents.extend(
                _read_linked_documents(root, skill_file, binding.command_skill_text)
            )
    except (OSError, ValueError) as exc:
        binding.command_error = (
            f"快捷命令 {command_name} 的技能 {skill_name} 无法加载：{exc}"
        )


def _read_linked_documents(root: Path, source: Path, text: str) -> list:
    """Load the transitive local Markdown references with finite bounds."""
    documents = []
    seen = {source.resolve()}
    pending = [(source, text)]
    total_bytes = len(text.encode("utf-8"))
    while pending:
        current, content = pending.pop(0)
        # Links in fenced code examples are documentation, not dependencies.
        prose = re.sub(r"```.*?```", "", content, flags=re.S)
        links = re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", prose)
        links += re.findall(r"^\[[^\]]+\]:\s*(\S+)", prose, re.M)
        for link in links:
            target = link.strip().split(' "', 1)[0].strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            relative = unquote(url.path)
            if "\\" in relative:
                raise ValueError(f"引用路径无效：{relative}")
            if not relative.lower().endswith(".md"):
                continue
            path = (current.parent / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"引用路径不在套件目录内：{relative}")
            if path in seen:
                continue
            seen.add(path)
            if len(seen) > 64:
                raise ValueError("套件引用文件超过 64 个")
            body = path.read_text(encoding="utf-8").strip()
            if not body:
                raise ValueError(f"引用文件为空：{relative}")
            total_bytes += len(body.encode("utf-8"))
            if total_bytes > 512 * 1024:
                raise ValueError("套件技能与引用正文超过 512KB")
            documents.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "status": "loaded",
                    "content": body,
                }
            )
            pending.append((path, body))
    return documents


def suite_message_reference(
    binding: Optional[SuiteBinding], ext_info: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Snapshot the resolved suite and command for this turn's message card."""
    if binding is None:
        return None
    display = (ext_info or {}).get("suite_display")
    return {
        "name": binding.name,
        "display": display if isinstance(display, str) and display else binding.name,
        "command": binding.command or None,
    }


def command_binding_event(binding: SuiteBinding) -> Dict[str, Any]:
    """Report instruction binding; this is not evidence of tool execution."""
    return {
        "type": "suite.bound",
        "suite": binding.name,
        "version": binding.version,
        "command": binding.command or None,
        "command_skill": binding.command_skill or None,
        "skill_loaded": bool(binding.command_skill_text) and not binding.command_error,
        "skill_sha256": (
            hashlib.sha256(binding.command_skill_text.encode("utf-8")).hexdigest()
            if binding.command_skill_text
            else None
        ),
        "command_error": binding.command_error or None,
        "semantic_status": binding.semantic_status,
        "package_format": binding.package_format,
        "documents": [
            {key: value for key, value in doc.items() if key != "content"}
            for doc in binding.loaded_documents
        ],
    }


def _probe_semantic_status(semantic: Dict[str, Any]) -> str:
    """Semantic layer is not implemented in-code yet: always degrade (P0)."""
    if not semantic:
        return "degraded"
    try:  # pragma: no cover - semantic serve module lands later
        import dbgpt_serve.semantic  # noqa: F401

        return "bound"
    except Exception:  # noqa: BLE001
        return "degraded"


def apply_suite_configuration(dialogue: Any) -> None:
    """Restore a configured resource before either engine builds its tools.

    This selects a resource only; normal datasource access checks still apply.
    """
    ext = dict(getattr(dialogue, "ext_info", None) or {})
    if ext.get("creation_mode") == "expert_suite" or ext.get("database_name"):
        return
    ref = resolve_suite_ref(ext)
    if not ref:
        return
    from dbgpt_serve.plugins.creation import SuiteCreationStore

    configured = SuiteCreationStore().configuration(ref)
    if configured.get("database_name"):
        ext["database_name"] = configured["database_name"]
        dialogue.ext_info = ext


def resolve_binding_for_turn(dialogue: Any) -> Optional[SuiteBinding]:
    """Resolve + record the suite pin for one chat turn (fail-soft)."""
    if (getattr(dialogue, "ext_info", None) or {}).get(
        "creation_mode"
    ) == "expert_suite":
        return None
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
        from dbgpt_serve.plugins.creation import SuiteCreationStore

        configured = SuiteCreationStore().configuration(ref)
        if configured.get("database_name"):
            ext_info = dict(ext_info or {})
            ext_info.setdefault("database_name", configured["database_name"])
            dialogue.ext_info = ext_info
        binding = load_binding(ref)
        if binding is None:
            logger.info("suite pin %s not enabled/installed; turn runs unbound", ref)
            return None
        command = (
            str(ext_info.get("suite_command") or "").strip()
            if isinstance(ext_info, dict)
            else ""
        )
        # Typed slash commands work too, including the UI's database prefix.
        if not command:
            text = str(getattr(dialogue, "user_input", "") or "")
            text = re.sub(r"^\[Database: [^\]]+\]\s*", "", text)
            for cmd in sorted(
                binding.commands,
                key=lambda item: len(item.get("name", "")),
                reverse=True,
            ):
                for candidate in [cmd["name"], *cmd.get("aliases", [])]:
                    if text == candidate or text.startswith(candidate + " "):
                        command = candidate
                        break
                if command:
                    break
            if not command:
                match = re.match(r"^(/\w[\w-]*)(?:\s|$)", text)
                command = match.group(1) if match else ""
        if command:
            bind_command(binding, command)
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
        if command:
            logger.info("suite command binding: %s", command_binding_event(binding))
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
    body = binding.sop_text.strip()
    if binding.package_format == "qwenwork-plugin":
        body = (
            "本套件以 plugin.json 与各 SKILL.md 为准。"
            "遵循套件声明的数据库及上下文要求；未连接时不得虚构采集结果。"
            "共享知识与参考文件按技能内链接读取，外部系统操作仍由核心权限和审批控制。\n"
            "可调用技能：\n"
            + "\n".join(
                f"- {cmd['name']}：{cmd.get('description', '')}"
                for cmd in binding.commands
            )
            + (f"\n\n{body}" if body else "")
        )
    body = body or "（本套件未携带 sop 文件）"
    watermark = f"\n\n> {binding.watermark}" if binding.watermark else ""
    command_block = ""
    if binding.command_error:
        command_block = (
            f"\n\n## 快捷命令不可用\n{binding.command_error}\n"
            "停止业务执行，向用户说明原因并请其重新选择命令。"
        )
    elif binding.command:
        command_block = (
            f"\n\n## 本轮快捷命令：{binding.command}\n"
            f"命令目标：{binding.command_description}\n"
            f"已从本套件加载知识技能：{binding.command_skill}。\n"
            "以下技能正文已直接加载，无需再次调用 load_skill。"
            "将用户问题作为命令参数，按该技能执行；工具仍受套件白名单与审批约束。"
            "只报告实际执行的操作，不能把技能加载当成任务完成。\n\n"
            f"### 知识技能 {binding.command_skill}\n{binding.command_skill_text}"
        )
    references = "".join(
        f"\n\n### 包内参考文件：{doc['path']}\n{doc['content']}"
        for doc in binding.loaded_documents
        if "content" in doc
    )
    return header + body + command_block + references + watermark


def make_suite_gate(binding: SuiteBinding):
    """Async gate fn with the same signature as the approval gate."""

    async def gate(name: str, args: dict) -> Optional[str]:  # noqa: ARG001
        if (
            _REPORT_AGENT_SCOPE.get()
            and name in _REPORT_AGENT_TOOLS
            and name not in binding.deny
            and binding.violation("generate_report") is None
        ):
            return None
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
