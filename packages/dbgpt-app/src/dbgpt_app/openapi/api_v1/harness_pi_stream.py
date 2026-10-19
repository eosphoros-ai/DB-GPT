"""pi harness engine streaming for the web agent chat.

Implements the pi branch of ``POST /v1/chat/react-agent``:
the turn runs on a ``pi --mode rpc`` subprocess through
:class:`PiHarnessRunner` while the neutral
:class:`HarnessEvent` stream is translated into the same
``step.*`` SSE vocabulary the dbgpt branch emits, so the
frontend needs zero engine awareness.

Persistence and terminal events mirror the dbgpt branch:
the conversation round is written to ``StorageConversation``
and closed with ``final`` + ``done`` SSE events.

Engine selection is driven by the request's
``ext_info.harness_engine``; availability is reported
through ``GET /v1/chat/harness/engines`` so the settings
UI can grey out unavailable engines.
"""

import asyncio
import glob
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import uuid
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Tuple,
)

from fastapi import Body, Header, HTTPException, Query
from fastapi.responses import FileResponse

from dbgpt._private.config import Config
from dbgpt.core import StorageConversation
from dbgpt_app.agent_harness.base import (
    HarnessEvent,
    HarnessEventKind,
)
from dbgpt_app.agent_harness.pi import (
    PiHarnessConfig,
    tool_bridge,
)
from dbgpt_app.agent_harness.registry import HARNESS_RUNNER_REGISTRY
from dbgpt_serve.conversation.serve import Serve as ConversationServe

from ..api_view_model import ConversationVo, Result
from .react_final import AgentFinalAnswer

logger = logging.getLogger(__name__)
CFG = Config()

#: Engines addressable from the frontend; dsh lands in P1.
KNOWN_ENGINES = ("dbgpt", "pi", "dsh")

#: Env var names driving the pi subprocess (no TOML yet).
ENV_PI_CLI = "DBGPT_HARNESS_PI_CLI"
ENV_PI_NODE = "DBGPT_HARNESS_PI_NODE"
ENV_PI_MODEL_API_BASE = "DBGPT_HARNESS_MODEL_API_BASE"
ENV_PI_MODEL_API = "DBGPT_HARNESS_MODEL_API"
ENV_PI_MODEL = "DBGPT_HARNESS_MODEL"
ENV_PI_EXCLUDED_TOOLS = "DBGPT_HARNESS_EXCLUDED_TOOLS"
ENV_PI_IDLE_TIMEOUT = "DBGPT_HARNESS_IDLE_TIMEOUT_S"
#: Env var name pi reads the model API key from (models.json
#: ``$NAME`` interpolation).
ENV_PI_API_KEY_ENV_NAME = "DBGPT_HARNESS_API_KEY_ENV_NAME"

_MAX_THOUGHT_CHARS = 16_000
_MAX_RESULT_CHARS = 4_000


# ---------------------------------------------------------------------------
# engine resolution & probes
# ---------------------------------------------------------------------------


def engine_availability() -> List[Dict[str, Any]]:
    """Availability manifest for the settings UI."""
    engines: List[Dict[str, Any]] = [
        {"engine": "dbgpt", "name": "DB-GPT", "available": True, "detail": ""}
    ]
    pi_ok, pi_detail = _probe_pi_cli()
    engines.append(
        {
            "engine": "pi",
            "name": "pi",
            "available": pi_ok,
            "detail": "" if pi_ok else pi_detail,
        }
    )
    engines.append(
        {
            "engine": "dsh",
            "name": "DSH",
            "available": False,
            "detail": "coming soon",
        }
    )
    return engines


# ---------------------------------------------------------------------------
# server-side engine preference (the source of truth
# for "which engine should run" — the request only
# carries an explicit override)
# ---------------------------------------------------------------------------


def _pref_file() -> str:
    work_dir = getattr(CFG.SYSTEM_APP, "work_dir", None) or os.getcwd()
    return os.path.join(work_dir, "harness_engine.json")


def get_harness_engine_pref() -> str:
    """Read the persisted engine preference."""
    try:
        with open(_pref_file(), encoding="utf-8") as f:
            data = json.load(f)
        engine = str(data.get("engine") or "").strip().lower()
        if engine in KNOWN_ENGINES:
            return engine
    except FileNotFoundError:
        pass
    except Exception:
        logger.warning("failed to read harness engine pref", exc_info=True)
    return "dbgpt"


def set_harness_engine_pref(engine: str) -> str:
    """Persist the engine preference; returns effective value."""
    normalized = str(engine or "").strip().lower()
    if normalized not in KNOWN_ENGINES:
        normalized = "dbgpt"
    try:
        with open(_pref_file(), "w", encoding="utf-8") as f:
            json.dump({"engine": normalized}, f)
    except Exception:
        logger.exception("failed to persist harness engine pref")
    return normalized


def resolve_harness_engine(dialogue: ConversationVo) -> str:
    """Engine pick: explicit request field, then the
    server-side preference."""
    ext_info = dialogue.ext_info if isinstance(dialogue.ext_info, dict) else {}
    engine = str(ext_info.get("harness_engine") or "").strip().lower()
    if engine in KNOWN_ENGINES:
        return engine
    return get_harness_engine_pref()


#: Fallback install locations discovered when neither
#: ``DBGPT_HARNESS_PI_CLI`` nor ``pi`` on PATH exist.
_PI_FALLBACK_INSTALLS = (
    os.path.expanduser(
        "~/.dbgpt/pi-runtime/lib/node_modules/"
        "@earendil-works/pi-coding-agent/dist/cli.js"
    ),
    "/tmp/pi-node/lib/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
)

#: pi requires Node >= 22.19 (hard requirement of the CLI).
_MIN_PI_NODE = (22, 19)


def _node_version_major_minor(node: str) -> Optional[Tuple[int, int]]:
    """Read a node binary's major.minor (None on failure)."""
    try:
        out = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.match(r"v?(\d+)\.(\d+)", out.stdout.strip())
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return None


def _candidate_nodes() -> List[str]:
    """Node binaries to consider, best first."""
    nodes: List[str] = []
    env_node = os.environ.get(ENV_PI_NODE)
    on_path = shutil.which("node")
    if env_node:
        nodes.append(env_node)
    if on_path:
        nodes.append(on_path)
    # nvm installs live outside PATH for server processes;
    # probe the newest versioned install.
    nvm_root = os.path.expanduser("~/.nvm/versions/node")
    if os.path.isdir(nvm_root):
        for entry in sorted(os.listdir(nvm_root), reverse=True):
            candidate = os.path.join(nvm_root, entry, "bin", "node")
            if os.path.isfile(candidate):
                nodes.append(candidate)
    return nodes


def _discover_pi() -> Tuple[Optional[str], Optional[str], str]:
    """Locate a usable pi CLI + node pair.

    Order: explicit env vars, ``pi`` on PATH, known
    install locations. Node must be >= 22.19; when the
    PATH node is too old, nvm installs are probed.

    Returns ``(pi_cli, node_path, detail)``; the two
    paths are ``None`` when discovery fails and
    ``detail`` explains why.
    """
    pi_cli: Optional[str] = os.environ.get(ENV_PI_CLI)
    if not pi_cli:
        on_path = shutil.which("pi")
        if on_path:
            pi_cli = on_path
    if not pi_cli:
        for candidate in _PI_FALLBACK_INSTALLS:
            if os.path.isfile(candidate):
                pi_cli = candidate
                break
    if not pi_cli:
        return None, None, "pi CLI not found"
    if not pi_cli.endswith((".js", ".mjs", ".cjs")):
        # native/shim executable; node not needed here.
        if not os.path.exists(pi_cli):
            return None, None, f"pi CLI not found ({pi_cli})"
        return pi_cli, None, ""

    for node in _candidate_nodes():
        version = _node_version_major_minor(node)
        if version is None:
            continue
        if version < _MIN_PI_NODE:
            continue
        return pi_cli, node, ""

    return (
        None,
        None,
        f"node >= {_MIN_PI_NODE[0]}.{_MIN_PI_NODE[1]} not found (pi requires it)",
    )


def _probe_pi_cli() -> Tuple[bool, str]:
    """Check pi CLI availability (and Node >= 22.19)."""
    pi_cli, _node, detail = _discover_pi()
    if pi_cli is None:
        return False, detail
    return True, pi_cli


def _format_question_result(pq: Any) -> str:
    """Same answer formatting as the dbgpt-engine question tool."""
    if pq.rejected:
        return "The user dismissed the question. Proceeding without answer."
    answers = pq.answers or []
    parts = []
    for i, q in enumerate(pq.questions):
        a_text = (
            ", ".join(answers[i]) if i < len(answers) and answers[i] else "Unanswered"
        )
        parts.append(f'"{q.get("question", "")}"="{a_text}"')
    return (
        f"User has answered your questions: {', '.join(parts)}."
        " You can now continue with the user's answers in mind."
    )


def _harness_internal_token() -> str:
    """Shared secret for the loopback tool-run endpoint.

    Mirrors the models.json dummy-key pattern: when the server defines
    ``API_KEYS`` the first key doubles as the harness token, otherwise a
    fixed internal value (loopback-only endpoint) is used.
    """
    api_keys = getattr(CFG, "API_KEYS", None)
    if api_keys:
        first = str(api_keys).split(",")[0].strip()
        if first:
            return first
    return "dbgpt-harness-internal"


def register_harness_endpoints(router: Any) -> None:
    """Attach the harness endpoint set to the api_v1 router."""

    @router.get("/v1/chat/harness/engines", response_model=Result)
    async def list_harness_engines() -> Result:
        """List selectable engines, availability, and
        the current server-side preference."""
        return Result.succ(
            {
                "engines": engine_availability(),
                "current": get_harness_engine_pref(),
            }
        )

    @router.put("/v1/chat/harness/engine", response_model=Result)
    async def set_harness_engine(
        payload: Dict[str, Any] = Body(),
    ) -> Result:
        """Persist the harness engine preference."""
        engine = set_harness_engine_pref(str(payload.get("engine") or "dbgpt"))
        return Result.succ({"engine": engine})

    @router.post("/v1/chat/harness/tool/run", response_model=Result)
    async def run_harness_tool(
        payload: Dict[str, Any] = Body(),
        authorization: Optional[str] = Header(default=None),
    ) -> Result:
        """Loopback executor for DB-GPT tools bridged into pi.

        The shipped pi extension posts ``{conv_id, tool, arguments}``
        here; the server-side per-conv ToolPack (same factories as the
        ReAct branch) executes the tool inside DB-GPT's containment.
        """
        bearer = (authorization or "").strip()
        if not bearer.lower().startswith("bearer ") or bearer[7:] != (
            _harness_internal_token()
        ):
            raise HTTPException(status_code=401, detail="invalid harness token")
        conv_id = str(payload.get("conv_id") or "")
        name = str(payload.get("tool") or "")
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        if not conv_id or not name:
            raise HTTPException(
                status_code=400, detail={"error": "conv_id and tool are required"}
            )
        if name == "question":
            # Async ask-user protocol: register the pending question, push
            # ``question.asked`` into the running turn's SSE stream and let
            # the pi extension poll /question/status for the answer.
            from .tools.question_manager import question_manager

            raw = arguments.get("questions")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = None
            if isinstance(raw, dict):
                raw = raw.get("questions")
            if not isinstance(raw, list) or not raw:
                raise HTTPException(
                    status_code=400, detail={"error": "questions list is required"}
                )
            pending = question_manager.create(conv_id=conv_id, questions=raw)
            tool_bridge.push_conv_event(
                conv_id,
                {
                    "type": "question.asked",
                    "request_id": pending.request_id,
                    "conv_id": conv_id,
                    "questions": raw,
                },
            )
            return Result.succ({"request_id": pending.request_id, "async": True})
        result = await tool_bridge.run_tool(conv_id, name, arguments)
        return Result.succ({"result": result})

    @router.get("/v1/chat/harness/question/status", response_model=Result)
    async def harness_question_status(
        request_id: str = Query(...),
        authorization: Optional[str] = Header(default=None),
    ) -> Result:
        """Polling endpoint for the pi question tool (loopback)."""
        bearer = (authorization or "").strip()
        if not bearer.lower().startswith("bearer ") or bearer[7:] != (
            _harness_internal_token()
        ):
            raise HTTPException(status_code=401, detail="invalid harness token")
        from .tools.question_manager import question_manager

        pq = question_manager.get(request_id)
        if pq is None:
            return Result.succ(
                {
                    "state": "gone",
                    "result": (
                        "Question expired or was already handled."
                        " Proceed without user answer."
                    ),
                }
            )
        if not pq.event.is_set():
            return Result.succ({"state": "pending"})
        result_text = _format_question_result(pq)
        frame_type = "question.rejected" if pq.rejected else "question.replied"
        conv_id = pq.conv_id
        question_manager.remove(pq.request_id)
        tool_bridge.push_conv_event(
            conv_id,
            {"type": frame_type, "request_id": pq.request_id, "conv_id": conv_id},
        )
        return Result.succ(
            {"state": "rejected" if pq.rejected else "answered", "result": result_text}
        )

    @router.get("/v1/chat/harness/artifact-file")
    async def harness_artifact_file(path: str = Query(...)) -> FileResponse:
        """Serve a generated artifact file (image thumbnails, ...) that is
        not covered by the static ``/images`` mount.

        Only paths resolving inside the generated-work roots are served
        (``PILOT_PATH`` — covers ``pilot/tmp/<conv>/`` charts and
        ``pilot/message/img`` — and ``<work_dir>/pi_workspace`` for pi
        writes). Anything else 404s, so source/config files stay private.
        ``<img>`` tags cannot send auth headers, hence open-but-scoped.
        """
        from dbgpt.configs.model_config import PILOT_PATH

        work_dir = getattr(CFG.SYSTEM_APP, "work_dir", None) or os.getcwd()
        roots = [
            os.path.realpath(PILOT_PATH),
            os.path.realpath(os.path.join(work_dir, "pi_workspace")),
        ]
        raw = (path or "").strip()
        if not raw:
            raise HTTPException(status_code=400, detail="path required")
        candidates = (
            [raw]
            if os.path.isabs(raw)
            else [os.path.join(root, raw) for root in roots]
            + [
                hit
                for root in roots
                for depth in ("*", "*/*")
                for hit in glob.glob(os.path.join(root, depth, raw))
            ]
        )
        resolved: Optional[str] = None
        for cand in candidates:
            real = os.path.realpath(cand)
            if not any(
                real == root or real.startswith(root + os.sep) for root in roots
            ):
                continue
            if os.path.isfile(real):
                resolved = real
                break
        if not resolved:
            raise HTTPException(status_code=404, detail="artifact file not found")
        media_type = mimetypes.guess_type(resolved)[0] or "application/octet-stream"
        return FileResponse(resolved, media_type=media_type)


# ---------------------------------------------------------------------------
# pi subprocess configuration (from environment)
# ---------------------------------------------------------------------------


def _resolve_model_config(default_model: str) -> Dict[str, Any]:
    """Decide how the pi subprocess reaches an LLM.

    Priority: explicit ``DBGPT_HARNESS_*`` env vars → an
    ambient anthropic-compatible gateway → DB-GPT's own
    OpenAI-compatible API (``/api/v2/chat/completions``,
    carrying the user's home-page model selection).
    """
    model = os.environ.get(ENV_PI_MODEL) or default_model
    model_api_base = os.environ.get(ENV_PI_MODEL_API_BASE)
    model_api = os.environ.get(ENV_PI_MODEL_API, "openai-completions")
    api_key_env = os.environ.get(ENV_PI_API_KEY_ENV_NAME, "DBGPT_HARNESS_MODEL_API_KEY")
    if not model_api_base and os.environ.get("ANTHROPIC_BASE_URL"):
        model_api_base = os.environ["ANTHROPIC_BASE_URL"]
        model_api = "anthropic-messages"
        if not model and os.environ.get("ANTHROPIC_MODEL"):
            model = os.environ["ANTHROPIC_MODEL"]
        if not os.environ.get(api_key_env) and os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            os.environ[api_key_env] = os.environ["ANTHROPIC_AUTH_TOKEN"]
        return {
            "model": model,
            "model_api_base": model_api_base,
            "model_api": model_api,
            "api_key_env": api_key_env,
        }
    if not model_api_base:
        # Default: point pi at this DB-GPT's agentic endpoint —
        # the OpenAI-compatible route that passes ``tools`` /
        # ``tool_choice`` through to the model. Models and
        # credentials stay inside DB-GPT's registry.
        web_port = getattr(CFG, "DBGPT_WEBSERVER_PORT", 5670)
        model_api_base = f"http://127.0.0.1:{web_port}/api/v2/v1/agentic"
        model_api = "openai-completions"
        api_keys = getattr(CFG, "API_KEYS", None)
        if api_keys and not os.environ.get(api_key_env):
            first_key = str(api_keys).split(",")[0].strip()
            os.environ[api_key_env] = first_key
        # pi requires an API key for every OpenAI-compatible
        # provider. DB-GPT's own /api/v2 accepts any bearer
        # when API_KEYS is unset, so use a dummy key that
        # pi can send without leaking real credentials.
        if not os.environ.get(api_key_env):
            os.environ[api_key_env] = "dbgpt-harness-internal"
    return {
        "model": model,
        "model_api_base": model_api_base,
        "model_api": model_api,
        "api_key_env": api_key_env,
    }


def build_pi_harness_config(
    conv_id: str, model_name: Optional[str] = None
) -> PiHarnessConfig:
    """Per-conv pi config for one conversation turn.

    The model defaults to the user's home-page selection so
    engine switching does not need extra model configuration.
    """
    work_dir = getattr(CFG.SYSTEM_APP, "work_dir", None) or os.getcwd()
    cwd = os.path.join(work_dir, "pi_workspace", conv_id)
    os.makedirs(cwd, exist_ok=True)
    excluded = [
        t.strip()
        for t in os.environ.get(ENV_PI_EXCLUDED_TOOLS, "bash").split(",")
        if t.strip()
    ]
    pi_cli, node_path, _detail = _discover_pi()
    if pi_cli is None:
        # Fall back to env/PATH defaults (probe would have
        # already reported the engine unavailable).
        pi_cli = os.environ.get(ENV_PI_CLI, "pi")
        node_path = None
    if pi_cli.endswith((".js", ".mjs", ".cjs")) and node_path is None:
        node_path = os.environ.get(ENV_PI_NODE) or shutil.which("node") or "node"

    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    idle_timeout = _env_float(ENV_PI_IDLE_TIMEOUT, 1800.0)
    model_cfg = _resolve_model_config(model_name or "")
    # When we bootstrap our own models.json the provider id
    # is "dbgpt"; pi rejects ambiguous model ids without an
    # explicit --provider.
    provider = "dbgpt" if model_cfg["model_api_base"] else None
    return PiHarnessConfig(
        pi_cli=pi_cli,
        node_path=node_path,
        cwd=cwd,
        provider=provider,
        model=model_cfg["model"],
        model_api_base=model_cfg["model_api_base"],
        model_api=model_cfg["model_api"],
        api_key_env=model_cfg["api_key_env"],
        excluded_tools=excluded,
        idle_timeout_s=idle_timeout,
        run_timeout_s=idle_timeout,
    )


# ---------------------------------------------------------------------------
# SSE helpers (mirrors the dbgpt branch's event shapes)
# ---------------------------------------------------------------------------


def _sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, max_len: int = 600) -> List[str]:
    if not text:
        return []
    return [text[start : start + max_len] for start in range(0, len(text), max_len)]


def _read_text_capped(path: str, cap: int = 200_000) -> Optional[str]:
    """Best-effort utf-8 read of a produced file (bounded), for previews."""
    try:
        if not path or not os.path.isfile(path):
            return None
        if os.path.getsize(path) > cap:
            return None
        with open(path, encoding="utf-8", errors="strict") as f:
            return f.read()
    except Exception:
        return None


def _embedded_artifact_outputs(text: str) -> List[Dict[str, Any]]:
    """Promote html/image chunks inside a ``{"chunks": [...]}`` tool-result
    envelope to typed outputs, so the artifact pipeline (cards, rail
    preview, persisted history) receives complete first-class payloads
    instead of display-capped envelope text."""
    stripped = (text or "").strip()
    if not stripped.startswith("{"):
        return []
    try:
        parsed = json.loads(stripped)
    except Exception:
        return []
    chunks = parsed.get("chunks") if isinstance(parsed, dict) else None
    if not isinstance(chunks, list):
        return []
    outputs: List[Dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        ctype = chunk.get("output_type")
        content = chunk.get("content")
        if ctype == "html" and isinstance(content, str) and content.strip():
            outputs.append(
                {
                    "output_type": "html",
                    "content": {
                        "content": content,
                        "title": chunk.get("title") or "Report",
                    },
                }
            )
        elif ctype == "image" and content:
            outputs.append({"output_type": "image", "content": content})
    return outputs


def _skills_prompt_block(preselected: Optional[str]) -> str:
    """List DB-GPT registry skills for the pi prompt.

    Same ``- name: description`` shape the ReAct system prompt uses;
    when a skill is pre-selected only that one is listed. Tells pi
    which tools read/run a skill (load_skill / get_skill_resource /
    execute_skill_script_file).
    """
    try:
        from dbgpt.agent.claude_skill import get_registry, load_skills_from_dir
        from dbgpt.configs.model_config import SKILLS_DIR

        load_skills_from_dir(SKILLS_DIR, recursive=True)
        skills = list(get_registry().list_skills())
        if not skills:
            return ""
        if preselected:
            matched = [s for s in skills if s.name.lower() == str(preselected).lower()]
            if matched:
                skills = matched
        lines = "\n".join(f"- {s.name}: {s.description}" for s in skills)
        return (
            "Available DB-GPT skills (use load_skill to read a skill's full "
            "instructions, get_skill_resource for its reference files, and "
            "execute_skill_script_file to run its scripts):\n" + lines
        )
    except Exception:
        logger.exception("pi harness: failed to build skills prompt block")
        return ""


def _build_pi_prompt(dialogue: ConversationVo, work_dir: Optional[str] = None) -> str:
    """Turn user input + selected resources into one pi prompt.

    pi is a coding-style agent: it needs concrete file paths and
    an explicit task, not just resource names. Uploaded files are
    referenced by absolute path (pi's ``read`` tool accepts them);
    pi's cwd is the per-conv workspace.
    """
    user_input = dialogue.user_input
    if not isinstance(user_input, str):
        user_input = str(user_input or "")
    ext_info = dialogue.ext_info if isinstance(dialogue.ext_info, dict) else {}
    ctx: List[str] = []

    file_path = ext_info.get("file_path")
    if file_path:
        ctx.append(
            f"- input data file: {file_path} "
            "(use your read tool to inspect it; analysis/report "
            "outputs go into the current working directory)"
        )
    skill_name = ext_info.get("skill_name")
    if skill_name:
        ctx.append(f"- apply the user-selected skill: {skill_name}")
    db_name = ext_info.get("database_name")
    if db_name:
        ctx.append(
            f"- connected database: {db_name} "
            f"(type: {ext_info.get('database_type') or 'unknown'})"
        )
    kb = (
        ext_info.get("knowledge_space_name")
        or ext_info.get("knowledge_space")
        or ext_info.get("knowledge_space_id")
    )
    if kb:
        ctx.append(f"- selected knowledge base: {kb}")

    if not ctx:
        base = user_input
    else:
        base = f"{user_input}\n\n—\nTask resources (from DB-GPT):\n" + "\n".join(ctx)
    skills_block = _skills_prompt_block(ext_info.get("skill_name"))
    if skills_block:
        base = f"{base}\n\n—\n{skills_block}"
    return base


# ---------------------------------------------------------------------------
# storage (mirrors the dbgpt branch's StorageConversation usage)
# ---------------------------------------------------------------------------


def _open_pi_storage_conv(
    dialogue: ConversationVo, conv_id: str
) -> Optional[StorageConversation]:
    try:
        conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
        storage_conv = StorageConversation(
            conv_uid=conv_id,
            chat_mode=dialogue.chat_mode or "chat_react_agent",
            user_name=dialogue.user_name,
            sys_code=dialogue.sys_code,
            summary=dialogue.user_input,
            app_code=dialogue.app_code,
            conv_storage=conv_serve.conv_storage,
            message_storage=conv_serve.message_storage,
        )
        storage_conv.save_to_storage()
        storage_conv.start_new_round()
        return storage_conv
    except Exception:
        logger.exception("pi harness: failed to open storage conversation")
        return None


def _write_pi_trace(
    conv_id: str,
    user_prompt: str,
    rounds: List[Dict[str, Any]],
    final_text: str,
) -> None:
    """Persist synthetic observability spans for one pi turn.

    Mirrors the agent-framework span shapes that
    ``ConversationTracePanel`` maps (``agent.generate_reply`` /
    ``agent.act.run``), so harness runs appear in the Trace tab
    alongside native dbgpt-engine traces.
    """
    try:
        from dbgpt.util.tracer.base import Span
        from dbgpt.util.tracer.sqlite_span_storage import SqliteSpanStorage

        storage = SqliteSpanStorage()
        trace_id = f"pi_{conv_id}_{uuid.uuid4().hex[:8]}"
        root_id = uuid.uuid4().hex
        root = Span(
            trace_id=trace_id,
            span_id=root_id,
            operation_name="agent.generate_reply",
            metadata={
                "conversation_id": conv_id,
                "received_message": {"content": user_prompt},
            },
        )
        root.end()
        storage.append_span(root)
        for rnd in rounds:
            span = Span(
                trace_id=trace_id,
                span_id=uuid.uuid4().hex,
                parent_span_id=root_id,
                operation_name="agent.act.run",
                metadata={"conversation_id": conv_id, "action_out": rnd},
            )
            span.end()
            storage.append_span(span)
        if final_text:
            term = Span(
                trace_id=trace_id,
                span_id=uuid.uuid4().hex,
                parent_span_id=root_id,
                operation_name="agent.act.run",
                metadata={
                    "conversation_id": conv_id,
                    "action_out": {
                        "action": "terminate",
                        "action_input": {"result": final_text},
                        "is_exe_success": True,
                    },
                },
            )
            term.end()
            storage.append_span(term)
    except Exception:
        logger.exception("pi harness: failed to write observability trace")


def _build_pi_history_payload(
    final_content: str,
    steps: List[Dict[str, Any]],
) -> str:
    """Same persisted-history shape as the dbgpt branch."""
    return json.dumps(
        {
            "version": 2,
            "protocol_version": 2,
            "type": "react-agent",
            "final_content": final_content,
            "citations": [],
            "steps": steps,
            "task_plan": [],
            "generated_images": [],
            "sub_agents": [],
            "input_files": [],
        },
        ensure_ascii=False,
    )


def _pi_terminal_events(
    storage_conv: Optional[StorageConversation],
    history_payload: str,
    final_answer: AgentFinalAnswer,
) -> Tuple[str, str]:
    """Persist the round, then produce final+done SSE without
    letting persistence errors kill the stream."""
    terminal = (
        _sse_event(final_answer.to_sse_payload()),
        _sse_event({"type": "done"}),
    )
    if storage_conv is not None:
        try:
            storage_conv.add_view_message(history_payload)
            storage_conv.end_current_round()
            storage_conv.save_to_storage()
        except Exception:
            logger.exception("pi harness: failed to persist round")
    return terminal


# ---------------------------------------------------------------------------
# event translation (HarnessEvent -> step.* SSE)
# ---------------------------------------------------------------------------


class _PiSessionState:
    """Translation state for one pi turn."""

    def __init__(self) -> None:
        self.step_count = 0
        self.round_no = 0
        self.thought_buffer = ""
        #: write/edit args captured at TOOL_START (keyed by tool_call_id
        #: — pi may execute tool calls in parallel, so events interleave)
        #: so TOOL_END can synthesize first-class file artifacts.
        self.pending_files: Dict[str, Dict[str, Any]] = {}
        #: tool_call_id -> step record so parallel tool_execution_end
        #: events still find their record after a sibling closed it.
        self.call_step_map: Dict[str, Dict[str, Any]] = {}
        #: pi child cwd, used to resolve relative tool paths.
        self.cwd = ""
        #: The live "思考中" step for the current turn
        #: (streamed via thought chunks, closed on tool/final).
        self.thought_step: Optional[Dict[str, Any]] = None
        #: round -> its running step record
        self.round_step_map: Dict[int, Dict[str, Any]] = {}
        self.history_steps: List[Dict[str, Any]] = []
        self.final_text = ""
        self.done = False
        self.aborted = False

    def close_thought_step(self) -> List[str]:
        """Close the pending thinking step, if any."""
        if self.thought_step is None:
            return []
        record = self.thought_step
        self.thought_step = None
        record["status"] = "done"
        record["thought"] = self.thought_buffer
        self.history_steps.append(record)
        return [_sse_event({"type": "step.done", "id": record["id"], "status": "done"})]

    def build_step(self, title: str, detail: str) -> Tuple[str, str, Dict[str, Any]]:
        """Return (step_id, step.start SSE, record)."""
        self.step_count += 1
        step_id = f"step-{self.step_count}"
        event = _sse_event(
            {
                "type": "step.start",
                "step": self.step_count,
                "id": step_id,
                "title": title,
                "detail": detail,
            }
        )
        record = {
            "id": step_id,
            "title": title,
            "detail": detail,
            "thought": "",
            "action": None,
            "action_input": None,
            "outputs": [],
            "status": "running",
        }
        return step_id, event, record


def _translate_event(
    state: _PiSessionState,
    ev: HarnessEvent,
) -> List[str]:
    """Map one HarnessEvent to zero or more SSE frames."""
    kind = ev.kind
    if kind == HarnessEventKind.TURN_START:
        state.round_no = ev.round or state.round_no + 1
        state.thought_buffer = ""
        return []

    if kind == HarnessEventKind.THINKING_DELTA:
        # Stream thinking to the frontend: create a "思考中"
        # step on first delta, then push each delta as a
        # step.chunk (thought) so the UI shows the assistant
        # reasoning growing live (DSH-style).
        frames: List[str] = []
        if state.thought_step is None:
            step_id, start_event, record = state.build_step(
                "思考中", "pi agent thinking"
            )
            state.thought_step = record
            frames.append(start_event)
        state.thought_buffer = (state.thought_buffer + ev.text)[:_MAX_THOUGHT_CHARS]
        frames.append(
            _sse_event(
                {
                    "type": "step.chunk",
                    "id": state.thought_step["id"],
                    "output_type": "thought",
                    "content": ev.text,
                }
            )
        )
        return frames

    if kind == HarnessEventKind.TOOL_START:
        title = ev.tool_name or "tool"
        if ev.tool_name in ("write", "edit"):
            args = (ev.data or {}).get("args") or {}
            content = args.get("content")
            call_id = str((ev.data or {}).get("tool_call_id") or "") or ev.tool_name
            state.pending_files[call_id] = {
                "path": str(args.get("path") or ""),
                "content": content if isinstance(content, str) else None,
            }
        # Close the streaming thought step before the tool
        # step begins (thought is attached to the tool step
        # via step.meta, same as the dbgpt branch).
        start_frames: List[str] = state.close_thought_step()
        record = state.round_step_map.get(state.round_no)
        if record is None:
            step_id, start_event, record = state.build_step(title, "pi agent tool")
            state.round_step_map[state.round_no] = record
            start_frames.append(start_event)
        else:
            step_id = record["id"]
        record["title"] = title
        record["action"] = ev.tool_name
        record["_open_calls"] = record.get("_open_calls", 0) + 1
        start_call_id = str((ev.data or {}).get("tool_call_id") or "") or title
        state.call_step_map[start_call_id] = record
        record["thought"] = state.thought_buffer
        # thought-only rounds end where the tool begins
        thought = state.thought_buffer or None
        state.thought_buffer = ""
        start_frames.append(
            _sse_event(
                {
                    "type": "step.meta",
                    "id": step_id,
                    "thought": thought,
                    "action_intention": None,
                    "action_reason": None,
                    "action": ev.tool_name,
                    "action_input": ev.data.get("args")
                    if isinstance(ev.data, dict)
                    else None,
                    "title": title,
                }
            )
        )
        return start_frames

    if kind == HarnessEventKind.TOOL_END:
        end_call_id = str((ev.data or {}).get("tool_call_id") or "") or (
            ev.tool_name or ""
        )
        record = state.call_step_map.pop(end_call_id, None) or state.round_step_map.get(
            state.round_no
        )
        if record is None:
            return []
        full_text = ev.text or ""
        detail = (
            full_text
            if len(full_text) <= _MAX_RESULT_CHARS
            else ((full_text[:_MAX_RESULT_CHARS] + "…[truncated]") if full_text else "")
        )
        frames: List[str] = []
        if detail:
            for chunk in _chunk_text(detail):
                frames.append(
                    _sse_event(
                        {
                            "type": "step.chunk",
                            "id": record["id"],
                            "output_type": "text",
                            "content": chunk,
                        }
                    )
                )
            record["outputs"].append({"output_type": "text", "content": detail})
        # Promote html/image payloads embedded in the result envelope to
        # first-class typed outputs (uncapped) so artifact cards/previews
        # get complete payloads both live and from persisted history.
        for embedded in _embedded_artifact_outputs(full_text):
            frames.append(
                _sse_event(
                    {
                        "type": "step.chunk",
                        "id": record["id"],
                        "output_type": embedded["output_type"],
                        "content": embedded["content"],
                    }
                )
            )
            record["outputs"].append(embedded)
        # write/edit successes become first-class file artifacts so the
        # stream cards / rail gallery express every produced file (md,
        # scripts, skill trees, ...), not just html reports.
        call_id = end_call_id
        pending = state.pending_files.pop(call_id, None)
        logger.info(
            "pi trace-dbg TOOL_END %s cid=%s pending=%s keys=%s is_error=%s",
            ev.tool_name,
            call_id,
            bool(pending),
            list(state.pending_files.keys()),
            bool(ev.data.get("is_error")),
        )
        if pending and pending.get("path") and not bool(ev.data.get("is_error")):
            path = pending["path"]
            if not os.path.isabs(path) and state.cwd:
                path = os.path.join(state.cwd, path)
            name = path.rstrip("/").split("/")[-1] or path
            content = pending.get("content")
            if content is None:
                # edit (or write without echoed content): read the final
                # file from disk so previews still have a payload.
                content = _read_text_capped(path)
            file_blob: Dict[str, Any] = {
                "name": name,
                "file_path": path,
                "size": len(content) if content else None,
            }
            if content and len(content) <= 200_000:
                file_blob["content"] = content
            frames.append(
                _sse_event(
                    {
                        "type": "step.chunk",
                        "id": record["id"],
                        "output_type": "file",
                        "content": file_blob,
                    }
                )
            )
            record["outputs"].append({"output_type": "file", "content": file_blob})
        record["_open_calls"] = record.get("_open_calls", 1) - 1
        if record["_open_calls"] <= 0:
            status = "failed" if bool(ev.data.get("is_error")) else "done"
            frames.append(
                _sse_event({"type": "step.done", "id": record["id"], "status": status})
            )
            record["status"] = status
            state.history_steps.append(record)
            state.round_step_map.pop(state.round_no, None)
        return frames

    if kind == HarnessEventKind.MESSAGE_END:
        if ev.text.strip():
            state.final_text = ev.text
        return []

    if kind == HarnessEventKind.RETRY:
        logger.info("pi harness retry: %s", ev.text[:200])
        return []

    if kind == HarnessEventKind.ERROR:
        logger.warning("pi harness error event: %s", ev.text[:200])
        return []

    if kind == HarnessEventKind.SETTLED:
        state.done = True
        state.aborted = bool(ev.data.get("aborted"))
        # Close the streaming thought step so the "思考中"
        # card is completed even when the turn had no tools.
        return state.close_thought_step()

    return []


def _close_dangling_steps(state: _PiSessionState) -> List[str]:
    """Close steps still running (e.g. final round had no tools)."""
    frames: List[str] = []
    for record in list(state.round_step_map.values()):
        if record["status"] == "running":
            frames.append(
                _sse_event({"type": "step.done", "id": record["id"], "status": "done"})
            )
            record["status"] = "done"
            state.history_steps.append(record)
        state.round_step_map.clear()
    return frames


# ---------------------------------------------------------------------------
# stream impl
# ---------------------------------------------------------------------------


_SENTINEL = object()


async def run_pi_harness_turn(
    dialogue: ConversationVo,
) -> AsyncGenerator[str, None]:
    """Run one react-agent turn on the pi harness engine.

    Emits the exact ``step.*`` vocabulary the dbgpt branch
    uses, persists the round, and closes with ``final``/``done``.
    """
    user_input = dialogue.user_input
    if not isinstance(user_input, str):
        user_input = str(user_input or "")
    conv_id = dialogue.conv_uid or ""
    engine_requested = resolve_harness_engine(dialogue)

    # Fail fast, before the agent stream starts, when the
    # requested engine is not available in this deployment.
    if engine_requested != "dbgpt":
        detail = ""
        available = False
        for e in engine_availability():
            if e["engine"] == engine_requested:
                available = e["available"]
                detail = e["detail"]
        if not available:
            msg = (
                f"引擎 {engine_requested} 当前不可用：{detail or '未启用'}。"
                "请改用 DB-GPT 引擎或在 Setting 中重新选择。"
            )
            storage_conv = _open_pi_storage_conv(dialogue, conv_id)
            for frame in _pi_terminal_events(
                storage_conv,
                _build_pi_history_payload(msg, []),
                AgentFinalAnswer(content=msg),
            ):
                yield frame
            return

    storage_conv = _open_pi_storage_conv(dialogue, conv_id)
    if storage_conv is not None:
        storage_conv.add_user_message(user_input)
    # Storage stays optional: without it the turn still
    # streams, only the history persistence is skipped.

    # Bridge DB-GPT built-in tools (sql_query / code_interpreter / ...)
    # into pi for this conversation; the manifest travels to the pi
    # extension via env at runner creation.
    manifest = tool_bridge.register_conv_tools(
        conv_id, dialogue.ext_info, CFG.SYSTEM_APP
    )

    def _pi_config_factory() -> PiHarnessConfig:
        cfg = build_pi_harness_config(conv_id, model_name=dialogue.model_name)
        cfg.prepare_agent_dir()
        if manifest and cfg.agent_dir and tool_bridge.install_extension(cfg.agent_dir):
            web_port = getattr(CFG, "DBGPT_WEBSERVER_PORT", 5670)
            cfg.extra_env = {
                "DBGPT_TOOLS_MANIFEST": json.dumps(manifest, ensure_ascii=False),
                "DBGPT_TOOLS_RUN_URL": (
                    f"http://127.0.0.1:{web_port}/api/v1/chat/harness/tool/run"
                ),
                "DBGPT_TOOLS_STATUS_URL": (
                    f"http://127.0.0.1:{web_port}/api/v1/chat/harness/question/status"
                ),
                "DBGPT_TOOLS_TOKEN": _harness_internal_token(),
                "DBGPT_TOOLS_CONV_ID": conv_id,
            }
            # The --tools allowlist (exclusion emulation) applies to
            # extension tools too — list the bridged names explicitly.
            cfg.tool_allowlist_extra = [m["name"] for m in manifest]
        return cfg

    try:
        runner = await HARNESS_RUNNER_REGISTRY.get(
            "pi",
            conv_id,
            _pi_config_factory,
        )
    except Exception as e:
        logger.exception("pi harness: failed to create runner")
        msg = f"pi harness init failed: {e}"
        for frame in _pi_terminal_events(
            storage_conv,
            _build_pi_history_payload(msg, []),
            AgentFinalAnswer(content=msg),
        ):
            yield frame
        return

    state = _PiSessionState()
    side_queue: asyncio.Queue = asyncio.Queue()
    tool_bridge.bind_conv_side_queue(conv_id, side_queue)
    state.cwd = os.path.join(
        getattr(CFG.SYSTEM_APP, "work_dir", None) or os.getcwd(),
        "pi_workspace",
        conv_id,
    )
    run_error: List[BaseException] = []
    out_queue: asyncio.Queue = asyncio.Queue()

    # Observability: synthesize agent-framework-shaped spans for pi turns
    # so the Trace tab has data for harness runs too.
    trace_rounds: List[Dict[str, Any]] = []
    pending_tool: Dict[str, Any] = {}

    async def _sink(ev: HarnessEvent) -> None:
        if ev.kind == HarnessEventKind.TOOL_START:
            pending_tool.clear()
            pending_tool.update(
                {
                    "action": ev.tool_name,
                    "action_input": (ev.data or {}).get("args"),
                }
            )
        elif ev.kind == HarnessEventKind.TOOL_END:
            # Attach the reasoning accumulated for this round (reset each
            # TURN_START) so the Trace panel shows a thought bubble before the
            # tool call — closer parity with the native dbgpt-engine trace,
            # which carries agent.act.run thoughts.
            thoughts = (state.thought_buffer or "").strip()
            round_out: Dict[str, Any] = {
                "action": ev.tool_name or pending_tool.get("action"),
                "action_input": pending_tool.get("action_input"),
                "observations": ev.text or "",
                "is_exe_success": not bool((ev.data or {}).get("is_error")),
            }
            if thoughts:
                round_out["thoughts"] = thoughts
            trace_rounds.append(round_out)
            pending_tool.clear()
        for frame in _translate_event(state, ev):
            await out_queue.put(frame)

    async def _forward_side() -> None:
        while True:
            item = await side_queue.get()
            if item is None:
                break
            await out_queue.put(_sse_event(item))

    side_task = asyncio.ensure_future(_forward_side())

    async def _drive() -> None:
        try:
            await runner.run(_build_pi_prompt(dialogue), on_event=_sink)
        except Exception as e:
            logger.exception("pi harness run failed")
            run_error.append(e)
        for frame in _close_dangling_steps(state):
            await out_queue.put(frame)
        await out_queue.put(_SENTINEL)

    drive_task = asyncio.ensure_future(_drive())
    try:
        while True:
            item = await out_queue.get()
            if item is _SENTINEL:
                break
            yield item
    except GeneratorExit:
        drive_task.cancel()
        side_task.cancel()
        tool_bridge.unbind_conv_side_queue(conv_id)
        raise
    except asyncio.CancelledError:
        drive_task.cancel()
        side_task.cancel()
        tool_bridge.unbind_conv_side_queue(conv_id)
        raise
    finally:
        side_queue.put_nowait(None)
        tool_bridge.unbind_conv_side_queue(conv_id)
    if run_error:
        final_content = f"pi harness failed: {run_error[0]}"
    elif state.aborted:
        final_content = state.final_text or "任务已中止。"
    else:
        final_content = state.final_text or "（pi 引擎未返回文本）"
    _write_pi_trace(conv_id, _build_pi_prompt(dialogue), trace_rounds, final_content)
    for frame in _pi_terminal_events(
        storage_conv,
        _build_pi_history_payload(final_content, state.history_steps),
        AgentFinalAnswer(content=final_content),
    ):
        yield frame
