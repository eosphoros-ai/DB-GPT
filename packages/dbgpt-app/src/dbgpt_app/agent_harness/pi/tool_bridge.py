"""Bridge DB-GPT agent built-in tools into the pi harness engine.

pi only ships its own coding tools (read/edit/write/...), so data-plane
capabilities of the platform (``sql_query``, ``code``,
``html_interpreter``, knowledge retrieval, ...) never reach a pi turn.
This module closes that gap in three pieces:

1. :func:`register_conv_tools` builds the same per-conv ``ToolPack`` the
   ReAct branch uses (shared factories from ``react_tools`` /
   ``agent_runner``) and caches it keyed by ``conv_id``;
2. :func:`install_extension` drops a generated-dir copy of the shipped
   pi extension (``extensions/dbgpt_tools.ts``) into the isolated pi
   agent dir, where pi auto-discovers it and registers one native tool
   per manifest entry;
3. :func:`run_tool` executes a tool server-side; the extension calls it
   through the loopback ``POST /v1/chat/harness/tool/run`` endpoint.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: todowrite manifest description (mirrors tools/todowrite.py).
_TODOWRITE_DESCRIPTION = (
    "Create and manage a structured task list for the current session. "
    "Use this tool to plan complex tasks (3+ steps) or tasks containing "
    "2 or more mutually independent subtasks, track progress, and show "
    "the user what you are doing. "
    "Pass the FULL todo list every time (not incremental). "
    "Each todo has: content (brief description), "
    "status (pending | in_progress | completed | cancelled), "
    "priority (high | medium | low). "
    "Rules: only ONE task in_progress at a time; mark tasks completed "
    "immediately after finishing; do NOT use for single trivial tasks. "
    "IMPORTANT: You MUST call todowrite again after EACH task completes to "
    "update status. The user sees progress in real time — never skip an "
    "update, and never end the turn while finished work is still pending "
    "or in_progress."
    '\nParameter: {"todos": [{"content": "...", "status": "...", '
    '"priority": "..."}]}'
)

#: Seconds a per-conv tool context stays cached without use.
_TTL_S = 6 * 3600
#: Cap on cached conv contexts (oldest evicted first).
_MAX_CONVS = 64

_REGISTRY: Dict[str, Dict[str, Any]] = {}

#: Per-conv side-channel queues for out-of-band SSE frames (question.asked
#: and friends) pushed while a pi turn is streaming.
_SIDE_QUEUES: Dict[str, Any] = {}

#: Per-conv round model (from the chat request) so loopback gates such as the
#: approval intent analyzer can reuse the same LLM the turn is running on.
_CONV_MODEL: Dict[str, str] = {}


def bind_conv_side_queue(conv_id: str, queue: Any) -> None:
    _SIDE_QUEUES[conv_id] = queue


def unbind_conv_side_queue(conv_id: str) -> None:
    _SIDE_QUEUES.pop(conv_id, None)
    _CONV_MODEL.pop(conv_id, None)


def set_conv_model(conv_id: str, model: Optional[str]) -> None:
    if model:
        _CONV_MODEL[conv_id] = str(model)


def get_conv_model(conv_id: str) -> Optional[str]:
    return _CONV_MODEL.get(conv_id)


def push_conv_event(conv_id: str, payload: Dict[str, Any]) -> bool:
    """Queue an out-of-band SSE payload for the conv's running turn."""
    queue = _SIDE_QUEUES.get(conv_id)
    if queue is None:
        return False
    queue.put_nowait(payload)
    return True


#: Tools exposed to pi when their prerequisite resource is selected.
#: Execution-class pi built-ins stay excluded; these run server-side
#: inside DB-GPT's sandbox/connector containment.
_CORE_TOOLS = (
    "sql_query",
    "code",
    "bash",
    "html_interpreter",
    "web_search",
    "web_fetch",
)


def _make_get_skill_resource(system_app: Any) -> Any:
    """``get_skill_resource`` with the same shape as the ReAct branch's
    module-level tool: read non-script reference files from a skill."""
    from dbgpt.agent.resource.tool.base import tool

    @tool(
        description="获取技能资源文件内容。"
        "根据路径读取技能中的参考文档、配置文件等非脚本资源。"
        '参数: {"skill_name": "技能名称", "resource_path": "资源路径"}'
        "\\n示例:"
        '\\n- 读取参考文档: {"skill_name": "my-skill", '
        '"resource_path": "references/analysis_framework.md"}'
        "\n注意: 执行脚本请使用 bash 工具"
    )
    async def get_skill_resource(skill_name: str, resource_path: str) -> str:
        from dbgpt.agent.skill.manage import get_skill_manager

        try:
            sm = get_skill_manager(system_app)
            return await sm.get_skill_resource(skill_name, resource_path, {})
        except Exception as e:
            return json.dumps(
                {"error": True, "message": f"Error: {str(e)}"},
                ensure_ascii=False,
            )

    return get_skill_resource


def _skill_tools(system_app: Any, react_state: Dict[str, Any]) -> List[Any]:
    """The dbgpt-engine skill family (read SKILL.md / reference files /
    run skill scripts), built from the SAME factories the ReAct branch
    uses so both engines expose identical skill capability."""
    from dbgpt.agent.claude_skill import get_registry, load_skills_from_dir
    from dbgpt.configs.model_config import SKILLS_DIR
    from dbgpt_app.openapi.api_v1.tools.skill_tools import (
        make_execute_skill_script_file,
        make_load_skill,
    )

    load_skills_from_dir(SKILLS_DIR, recursive=True)
    if not get_registry().list_skills():
        return []
    return [
        make_load_skill(react_state),
        _make_get_skill_resource(system_app),
        make_execute_skill_script_file(react_state),
    ]


#: Valid JSON-Schema primitive types accepted by strict validators
#: (DeepSeek/OpenAI reject DB-GPT's comma-joined union strings such as
#: ``"object, string"`` produced from ``dict | str`` annotations).
_JSON_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}


def _json_type_spec(raw: Optional[str]) -> Dict[str, Any]:
    """Convert a ToolParameter type string into a valid JSON-Schema fragment."""
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    valid = [p for p in parts if p in _JSON_TYPES]
    if len(valid) == 1:
        spec: Dict[str, Any] = {"type": valid[0]}
        if valid[0] == "array":
            # OpenAI-style validators require ``items`` on array schemas.
            spec["items"] = {}
        return spec
    if len(valid) > 1:
        return {
            "anyOf": [
                {"type": t, **({"items": {}} if t == "array" else {})} for t in valid
            ]
        }
    return {}  # unknown/missing type: leave the property unconstrained


def _tool_schema(tool: Any) -> Dict[str, Any]:
    """OpenAI/JSON-schema shape of a BaseTool's args (pi-facing)."""
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for key, value in tool.args.items():
        properties[key] = {
            **_json_type_spec(getattr(value, "type", None)),
            "description": value.description,
        }
        if value.required:
            required.append(key)
    return {"type": "object", "properties": properties, "required": required}


def _evict_expired() -> None:
    now = time.time()
    for key in [k for k, v in _REGISTRY.items() if now - v["ts"] > _TTL_S]:
        _REGISTRY.pop(key, None)
        _CONV_MODEL.pop(key, None)
    if len(_REGISTRY) > _MAX_CONVS:
        oldest = sorted(_REGISTRY, key=lambda k: _REGISTRY[k]["ts"])
        for key in oldest[: len(_REGISTRY) - _MAX_CONVS]:
            _REGISTRY.pop(key, None)


def register_conv_tools(
    conv_id: str,
    ext_info: Optional[Dict[str, Any]],
    system_app: Any,
    react_state_extra: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build/cache the per-conv ToolPack and return its pi manifest.

    Returns an empty list when the conversation selected no resource
    that maps to a DB-GPT tool (pi then runs with its built-ins only).
    ``react_state_extra`` overlays per-turn state (e.g. staged upload
    paths) onto the react_state handed to the bridged tools.
    """
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.subagent.react_tools import make_react_tools
    from dbgpt_app.openapi.api_v1.tools.kb_tools import make_kb_tools

    ext = ext_info if isinstance(ext_info, dict) else {}
    datasources = [d for d in [ext.get("database_name")] if d]
    knowledge = [
        k
        for k in [
            ext.get("knowledge_space_name")
            or ext.get("knowledge_space")
            or ext.get("knowledge_space_id")
        ]
        if k
    ]

    connector = None
    if datasources:
        try:
            from dbgpt_serve.datasource.manages import ConnectorManager

            manager = ConnectorManager.get_instance(system_app)
            connector = manager.get_connector(datasources[0])
        except Exception as e:
            logger.warning(
                "pi tool bridge: load connector %s failed: %s", datasources[0], e
            )

    react_state: Dict[str, Any] = {"conv_id": conv_id, "file_path": None}
    if react_state_extra:
        react_state.update(react_state_extra)
    # Carried into query artifacts so the edit & re-run endpoint can
    # re-resolve the connector (gpts_conversations does not persist ext_info).
    if datasources:
        react_state["database_name"] = datasources[0]
    factory = make_react_tools(
        react_state,
        database_connector=connector,
        knowledge_resources=None,
    )
    # Execution tools are always bridged (same containment as the dbgpt
    # engine: sandboxed code/shell, server-side html render), so bare
    # conversations keep analysis capability; sql_query needs a database.
    tool_list: List[Any] = []
    for name in _CORE_TOOLS:
        if name == "sql_query" and not datasources:
            continue
        if name in factory:
            tool_list.append(factory[name])
    # KB family from the SAME factory as the ReAct branch (kb_ls/glob/
    # grep/cat/semantic + wiki + codegraph gating) for exact parity.
    if knowledge:
        try:
            tool_list.extend(make_kb_tools(knowledge[0]))
        except Exception as e:
            logger.warning("pi tool bridge: make_kb_tools failed: %s", e)
    # Skill family (load_skill / get_skill_resource /
    # execute_skill_script_file) so pi can read and run the platform's
    # installed skills, same as the dbgpt engine. Mounted only when the
    # registry actually has skills.
    try:
        tool_list.extend(_skill_tools(system_app, react_state))
    except Exception as e:
        logger.warning("pi tool bridge: skill tools unavailable: %s", e)

    pack = ToolPack(tool_list) if tool_list else None
    # ToolPack wraps plain callables into BaseTool instances; read the
    # manifest from the wrapped resources (name/description/args).
    manifest = [
        {
            "name": wrapped.name,
            "description": wrapped.description,
            "parameters": _tool_schema(wrapped),
        }
        for wrapped in (pack.sub_resources if pack else [])
    ]
    # ask-user parity with the dbgpt engine: the question tool is always
    # available; execution is handled by the loopback endpoint (polling
    # protocol), not by the ToolPack.
    from dbgpt_app.openapi.api_v1.tools.question import _DESCRIPTION

    manifest.append(
        {
            "name": "question",
            "description": _DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "string",
                        "description": (
                            "JSON string: list of {question, header, "
                            "options:[{label,description}], multiple?}"
                        ),
                    }
                },
                "required": ["questions"],
            },
        }
    )
    # Plan parity with the dbgpt engine: per-conv todo state + tool.
    from dbgpt_app.openapi.api_v1.tools.todowrite import make_todowrite

    todo_list: List[Dict[str, str]] = []
    todowrite_fn = make_todowrite(todo_list, lambda *a, **k: None)
    manifest.append(
        {
            "name": "todowrite",
            "description": _TODOWRITE_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "string",
                        "description": (
                            "JSON string: FULL list of {content, status, "
                            "priority} replacing the session plan"
                        ),
                    }
                },
                "required": ["todos"],
            },
        }
    )
    _REGISTRY[conv_id] = {
        "pack": pack,
        "manifest": manifest,
        "ts": time.time(),
        "todowrite": todowrite_fn,
        "todo_list": todo_list,
    }
    _evict_expired()
    logger.info(
        "pi tool bridge: conv %s exposes %s",
        conv_id,
        [m["name"] for m in manifest],
    )
    return manifest


def get_manifest(conv_id: str) -> List[Dict[str, Any]]:
    """Manifest cached for ``conv_id`` (empty when none/expired)."""
    entry = _REGISTRY.get(conv_id)
    if not entry or time.time() - entry["ts"] > _TTL_S:
        return []
    return entry["manifest"]


async def run_tool(conv_id: str, name: str, arguments: Dict[str, Any]) -> str:
    """Execute one bridged tool server-side; returns result text."""
    entry = _REGISTRY.get(conv_id)
    if not entry or time.time() - entry["ts"] > _TTL_S:
        return json.dumps(
            {"error": f"no DB-GPT tool context for conversation {conv_id}"},
            ensure_ascii=False,
        )
    entry["ts"] = time.time()
    if name == "todowrite":
        fn = entry.get("todowrite")
        if fn is None:
            return json.dumps({"error": "todowrite unavailable"}, ensure_ascii=False)
        raw = (arguments or {}).get("todos", "[]")
        return str(fn(raw if isinstance(raw, str) else json.dumps(raw)))
    try:
        result = await entry["pack"].async_execute(
            resource_name=name, **(arguments or {})
        )
        return str(result)
    except Exception as e:
        logger.exception("pi tool bridge: tool %s failed", name)
        return json.dumps(
            {"error": f"tool {name} execution failed: {e}"}, ensure_ascii=False
        )


def install_extension(agent_dir: str) -> Optional[str]:
    """Copy the shipped extension into pi's isolated agent dir.

    pi auto-discovers ``<agent_dir>/extensions/*.ts`` at startup (the
    agent dir replaces ``~/.pi/agent`` via ``PI_CODING_AGENT_DIR``).
    """
    src = os.path.join(os.path.dirname(__file__), "extensions", "dbgpt_tools.ts")
    if not os.path.isfile(src):
        logger.warning("pi tool bridge: extension source missing at %s", src)
        return None
    dst_dir = os.path.join(agent_dir, "extensions")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "dbgpt_tools.ts")
    try:
        with open(src, encoding="utf-8") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        return dst
    except Exception:
        logger.exception("pi tool bridge: failed to install extension")
        return None
