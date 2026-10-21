"""Lightweight single-task ReAct agent runner for TaskFlow agent nodes.

Extracted from the sub-agent dispatcher pattern
(``api_v1.subagent.dispatcher.build_sub_react_agent``) and generalized:

- **Profiles**: builtin system-prompt skeletons (data analysis / knowledge /
  general) instead of the dispatcher's single sub-agent template;
- **Scoped resources**: selected skills / datasources / knowledge spaces /
  MCP servers define the agent's capability boundary — an unselected resource
  simply does not appear in the action space (checkboxes ARE the boundary);
- **Step events**: the agent's ``stream_callback`` is mapped to
  :class:`AgentStepEvent` so callers can stream the ReAct trace live.

Isolation model (same as the dispatcher): independent ``conv_id`` (drives the
code-interpreter working directory), independent ``GptsMemory``, independent
tool set rebuilt per run. Nothing is shared except read-only connectors.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from dbgpt._private.config import Config

logger = logging.getLogger(__name__)

CFG = Config()

#: Factory tools that can be selected via the node's ``tools`` config.
SELECTABLE_TOOLS = [
    "sql_query",
    "code_interpreter",
    "knowledge_retrieve",
    "html_interpreter",
    "shell_interpreter",
    "web_search",
    "web_fetch",
]
#: Factory tools attached automatically when skills are selected.
SKILL_TOOLS = ["load_skill", "execute_skill_script_file"]

_FORBIDDEN_SQL_PREFIXES = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
)

_MAX_UPSTREAM_CHARS = 20_000


@dataclass
class AgentStepEvent:
    """One visible step inside an agent node's ReAct loop."""

    kind: str  # thinking | action | answer
    title: str
    detail: str = ""
    round: int = 0


#: ``(node label, node kind, content)`` sections handed to the agent.
UpstreamSection = Tuple[str, str, str]

StepCallback = Callable[[AgentStepEvent], Awaitable[None]]


_VIS_BLOCK_RE = re.compile(r"```vis-[a-z0-9_-]*\s*\n[\s\S]*?```")
_THOUGHT_RE = re.compile(
    r"Thought\s*[:：]\s*(.*?)(?=\n\s*(?:Action|Phase|Observation)\b|$)", re.DOTALL
)


def _clean_thought_text(llm_reply: str) -> str:
    """Reduce a raw ReAct llm_reply to just the thought narrative.

    The model adapter may wrap reasoning in ```vis-thinking blocks and the
    reply itself carries the full protocol scaffolding (Thought: / Action
    Intention: / Action: / Action Input:) — neither belongs in a step card.
    """
    text = _VIS_BLOCK_RE.sub("", llm_reply or "")
    match = _THOUGHT_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


_ACTION_INPUT_RE = re.compile(r"Action\s*Input\s*[:：]\s*", re.IGNORECASE)
_RESULT_FIELD_RE = re.compile(
    r'"(?:result|output)"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL
)


def _robust_final_answer(text: str) -> str:
    """Best-effort unwrap of a ReAct terminate envelope.

    ``_extract_final_answer`` (ReActOutputParser) bails to the raw text for
    long multi-line markdown results (invalid/over-long JSON). This fallback
    locates the last ``Action Input:`` block and pulls the ``result``/``output``
    string field out of it with a tolerant regex; if nothing matches, protocol
    header lines are stripped so the answer at least reads clean.
    """
    from ..openapi.api_v1.subagent.result import _extract_final_answer

    cleaned = _extract_final_answer(text)
    if "Action Input" not in cleaned and not cleaned.lstrip().startswith("Thought:"):
        return cleaned
    candidate = cleaned
    last = None
    for m in _ACTION_INPUT_RE.finditer(candidate):
        last = m
    if last is not None:
        tail = candidate[last.end() :]
        field = _RESULT_FIELD_RE.search(tail)
        if field:
            raw_value = field.group(1)
            try:
                return json.loads(f'"{raw_value}"').strip()
            except Exception:
                return raw_value.replace("\\n", "\n").replace('\\"', '"').strip()
    # Last resort: drop protocol header lines (Thought:/Action:/Action Input:).
    lines = []
    for line in candidate.splitlines():
        head = line.lstrip()
        if head.startswith(
            (
                "Thought:",
                "Action:",
                "Action Input:",
                "Action Intention:",
                "Action Reason:",
            )
        ):
            continue
        lines.append(line)
    return "\n".join(lines).strip() or cleaned


_ENVELOPE_START_RE = re.compile(r'^\s*\{\s*"chunks"')


def _envelope_readable(text: str, zh: bool = True) -> Optional[str]:
    """Reduce a raw tool envelope (``{"chunks": [...]}``) to readable text.

    Models occasionally terminate with the last tool observation pasted as
    the result; leaking the JSON payload into the answer area is useless.
    Returns ``None`` when ``text`` is not an envelope so callers can keep
    the original answer untouched.
    """
    if not text or _ENVELOPE_START_RE.match(text) is None:
        return None
    try:
        parsed = json.loads(text.strip())
    except Exception:
        return None
    chunks = parsed.get("chunks") if isinstance(parsed, dict) else None
    if not isinstance(chunks, list):
        return None
    parts: List[str] = []
    html_titles: List[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        output_type = chunk.get("output_type")
        content = chunk.get("content")
        if output_type == "html":
            html_titles.append(str(chunk.get("title") or "HTML"))
        elif (
            output_type in ("text", "markdown")
            and isinstance(content, str)
            and content.strip()
        ):
            parts.append(content.strip())
    if html_titles:
        # A rendered HTML report IS the deliverable; the tool's own
        # instruction text ("please terminate now…") is not user content.
        note = "HTML 报告已渲染: " if zh else "HTML report rendered: "
        return note + ", ".join(html_titles)
    return "\n\n".join(parts) if parts else None


@dataclass
class AgentProfile:
    """A builtin agent persona: system prompt skeleton + default tools."""

    profile_id: str
    label: str
    label_en: str
    desc: str
    desc_en: str
    default_tools: List[str] = field(default_factory=list)


_PROFILES: Dict[str, AgentProfile] = {
    "react_data": AgentProfile(
        profile_id="react_data",
        label="数据分析 Agent",
        label_en="Data Analysis Agent",
        desc="目标驱动的数据分析师,可用 SQL / 代码复核数字与口径",
        desc_en="Goal-driven data analyst; verifies numbers with SQL/code",
        default_tools=["sql_query", "code_interpreter"],
    ),
    "react_knowledge": AgentProfile(
        profile_id="react_knowledge",
        label="知识答疑 Agent",
        label_en="Knowledge QA Agent",
        desc="企业知识专家,先检索核实再回答,标注来源",
        desc_en="Knowledge expert; retrieves before answering, cites sources",
        default_tools=["knowledge_retrieve"],
    ),
    "react_general": AgentProfile(
        profile_id="react_general",
        label="通用任务 Agent",
        label_en="General Task Agent",
        desc="谨慎的通用执行者,按目标组织结论",
        desc_en="Careful general-purpose executor",
        default_tools=[],
    ),
}

_PROFILE_PROMPT_ZH = {
    "react_data": "你是一位资深数据分析师。以目标驱动完成任务,涉及数字与口径时,"
    "优先用 SQL 或代码复核,不凭记忆作答。",
    "react_knowledge": "你是企业知识专家。回答前必须先检索知识库核实,"
    "结论标注来源;查不到就明说,不编造。",
    "react_general": "你是一位谨慎的任务执行者。严格围绕目标产出,"
    "善用可用工具,结论简明自洽。",
}

_PROFILE_PROMPT_EN = {
    "react_data": "You are a senior data analyst. Work goal-driven; verify "
    "numbers and calibers with SQL or code instead of guessing.",
    "react_knowledge": "You are an enterprise knowledge expert. Always retrieve "
    "before answering and cite sources; say so when not found.",
    "react_general": "You are a careful task executor. Stay on the goal, use "
    "tools when helpful, keep conclusions concise.",
}


def list_agent_profiles() -> List[Dict[str, Any]]:
    """Return the builtin profile manifest for the agent-options endpoint."""
    return [
        {
            "id": p.profile_id,
            "label": p.label,
            "label_en": p.label_en,
            "desc": p.desc,
            "desc_en": p.desc_en,
            "default_tools": p.default_tools,
        }
        for p in _PROFILES.values()
    ]


def get_agent_profile(profile_id: Optional[str]) -> AgentProfile:
    """Resolve a profile id, falling back to the general profile."""
    return _PROFILES.get(profile_id or "") or _PROFILES["react_general"]


def list_builtin_tools() -> List[Dict[str, Any]]:
    """Return the selectable builtin tool manifest (zh/en labels)."""
    return [
        {
            "id": "sql_query",
            "label": "SQL 查询",
            "label_en": "SQL Query",
            "desc": "对选中数据源执行只读 SQL",
            "desc_en": "Read-only SQL on selected datasources",
        },
        {
            "id": "code_interpreter",
            "label": "代码解释器",
            "label_en": "Code Interpreter",
            "desc": "沙箱执行 Python 复核计算",
            "desc_en": "Sandboxed Python for calculations",
        },
        {
            "id": "knowledge_retrieve",
            "label": "知识库检索",
            "label_en": "Knowledge Retrieve",
            "desc": "检索选中知识库",
            "desc_en": "Retrieve from selected knowledge spaces",
        },
        {
            "id": "html_interpreter",
            "label": "HTML 生成",
            "label_en": "HTML Interpreter",
            "desc": "生成可视化 HTML 报告",
            "desc_en": "Generate visual HTML reports",
        },
        {
            "id": "shell_interpreter",
            "label": "Shell",
            "label_en": "Shell",
            "desc": "沙箱执行 shell 命令",
            "desc_en": "Sandboxed shell commands",
        },
    ]


def list_available_skills() -> List[Dict[str, Any]]:
    """Enumerate installed skills (builtin + user uploaded) for the manifest."""
    try:
        from dbgpt.agent.claude_skill import get_registry

        skills = []
        for s in get_registry().list_skills():
            meta = getattr(s, "metadata", None)
            name = getattr(meta, "name", None) or getattr(s, "name", "")
            desc = getattr(meta, "description", "") or ""
            skills.append({"name": name, "label": name, "desc": desc})
        return skills
    except Exception as e:
        logger.warning(f"list_available_skills failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE_ZH = """{persona}

你在一个工作流节点中独立运行,看不到主对话历史。你需要的一切都在下方的
目标与材料里。

## 可用工具
只能使用下列工具,工具名必须完全匹配。所有工具均为只读;如需写操作,
在结论中给出建议而不是执行。
{{{{ action_space }}}}
{skills_section}{resources_section}
## 规则
- 不能再派生子任务
- 保持上下文紧凑,结论简明自洽
- 完成后调用 terminate 给出最终答案

## 响应格式(ReAct)
每次响应必须恰好包含一个 Action 与一个 Action Input。
Action 必须是 [{{{{ action_space_names }}}}] 之一:
- Thought: 分析现状并决定下一步
- Action Intention: 本步要做什么(简短,面向用户)
- Action: 工具名(与上方完全一致)
- Action Input: JSON 参数(无参时为空)

任务完成时严格使用:
Thought: ...
Action: terminate
Action Input: {{"result": "最终答案"}}
"""

_SYSTEM_TEMPLATE_EN = """{persona}

You run independently inside one workflow node and cannot see the main
conversation. Everything you need is in the goal and materials below.

## Available tools
Use ONLY the tools below with EXACT names. All tools are read-only; if a
write is needed, recommend it in your conclusion instead of executing.
{{{{ action_space }}}}
{skills_section}{resources_section}
## Rules
- No further delegation
- Keep context tight; produce a concise, self-contained conclusion
- Call ``terminate`` with the final result when done

## Response format (ReAct)
Every response MUST contain exactly one Action and one Action Input.
The Action MUST be one of [{{{{ action_space_names }}}}].
- Thought: analyze the status and decide the next step
- Action Intention: what this step does (short, user-facing)
- Action: the tool name (exactly as listed)
- Action Input: JSON parameters (empty if none)

When finished, use exactly:
Thought: ...
Action: terminate
Action Input: {{"result": "final answer"}}
"""


def _build_skills_section(skill_names: List[str], zh: bool) -> str:
    if not skill_names:
        return ""
    try:
        from dbgpt.agent.claude_skill import get_registry

        registry = get_registry()
        lines = []
        for name in skill_names:
            skill = registry.get_skill(name)
            desc = ""
            if skill and getattr(skill, "metadata", None):
                desc = getattr(skill.metadata, "description", "") or ""
            lines.append(f"- {name}: {desc}".rstrip(": "))
    except Exception:
        lines = [f"- {name}" for name in skill_names]
    header = "## 可用技能\n" if zh else "## Available skills\n"
    hint = (
        "需要时通过 load_skill 加载技能说明,execute_skill_script_file 执行其脚本。\n\n"
        if zh
        else "Load details via load_skill; run scripts via "
        "execute_skill_script_file.\n\n"
    )
    return header + "\n".join(lines) + "\n" + hint


def _build_resources_section(
    datasources: List[str], knowledge: List[str], zh: bool
) -> str:
    parts = []
    if datasources:
        header = (
            "- 可查询数据源(只读): " if zh else "- Queryable datasources (read-only): "
        )
        parts.append(header + ", ".join(datasources))
    if knowledge:
        header = "- 可检索知识库: " if zh else "- Retrievable knowledge spaces: "
        parts.append(header + ", ".join(knowledge))
        hint = (
            "  (kb_ls 列文档清单、kb_glob 按名查找、kb_grep 搜内容、kb_cat 读文件、"
            "semantic_search 语义检索)"
            if zh
            else "  (kb_ls list docs, kb_glob find by name, kb_grep search contents, "
            "kb_cat read file, semantic_search semantic retrieval)"
        )
        parts.append(hint)
    if not parts:
        return ""
    header = "## 资源范围\n" if zh else "## Resource scope\n"
    return header + "\n".join(parts) + "\n\n"


def build_user_message(
    goal: str, question: str, upstream_sections: List[UpstreamSection]
) -> str:
    """Assemble the single user message (goal + question + sourced materials)."""
    parts = [goal.strip() or "完成用户的问题。", "", "用户问题:", question.strip()]
    if upstream_sections:
        parts += ["", "上游节点产出(按执行顺序):"]
        budget = _MAX_UPSTREAM_CHARS
        for label, kind, content in upstream_sections:
            block = (
                f'<source node="{label}" kind="{kind}">\n{content.strip()}\n</source>'
            )
            if budget - len(block) < 0:
                block = block[: max(budget, 0)] + "\n...(已截断)\n</source>"
            parts.append(block)
            budget -= len(block)
            if budget <= 0:
                parts.append("...(更多上游内容已省略)")
                break
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Scoped tools
# ---------------------------------------------------------------------------


def _make_multi_db_sql_tool(datasources: List[str], system_app: Any):
    """Build a read-only sql_query tool scoped to the selected datasources."""
    from dbgpt.agent.resource.tool.base import tool

    db_list = ", ".join(datasources)

    @tool(
        description=(
            f"对指定数据源执行只读 SQL 查询(仅 SELECT)。可用数据源: {db_list}。"
            '参数: {"sql": "SELECT 语句", "db_name": "数据源名(可选,默认第一个)"}'
        )
    )
    def sql_query(sql: str, db_name: Optional[str] = None) -> str:
        from dbgpt_serve.datasource.manages import ConnectorManager

        if not db_name and len(datasources) > 1:
            content = f"存在多个可用数据源,请显式指定 db_name 参数(可选: {db_list})"
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": content}]},
                ensure_ascii=False,
            )
        target = db_name or datasources[0]
        if target not in datasources:
            content = f"数据源 '{target}' 不在本节点可用范围: {db_list}"
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": content}]},
                ensure_ascii=False,
            )
        sql_upper = sql.strip().rstrip(";").upper().lstrip()
        for kw in _FORBIDDEN_SQL_PREFIXES:
            if sql_upper.startswith(kw):
                content = f"安全限制: 不允许执行 {kw} 语句,仅支持 SELECT。"
                return json.dumps(
                    {"chunks": [{"output_type": "text", "content": content}]},
                    ensure_ascii=False,
                )
        try:
            from ..openapi.api_v1.tools.query_artifact import (
                build_query_chunk,
                markdown_table,
                normalize_result,
            )

            manager = ConnectorManager.get_instance(system_app)
            connector = manager.get_connector(target)
            result = connector.run(sql.strip().rstrip(";"))
            if not result:
                text = "查询返回空结果。"
                return json.dumps(
                    {"chunks": [{"output_type": "text", "content": text}]},
                    ensure_ascii=False,
                )
            col_names, rows = normalize_result(result)
            # Query artifact (SQL + capped result set) first so the flow UI
            # can render the data artifact; the markdown table is what the
            # node agent reasons over.
            chunks = [
                build_query_chunk(
                    sql.strip().rstrip(";"), col_names, rows, db_name=target
                ),
                {
                    "output_type": "markdown",
                    "content": markdown_table(col_names, rows),
                },
            ]
            return json.dumps({"chunks": chunks}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": f"查询失败: {e}"}]},
                ensure_ascii=False,
            )

    return sql_query


def _load_knowledge_resources(space_names: List[str], system_app: Any) -> List[Any]:
    """Build retriever resources for the selected knowledge spaces."""
    resources = []
    if not space_names:
        return resources
    from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource

    for space in space_names:
        try:
            resources.append(
                KnowledgeSpaceRetrieverResource(
                    name=f"knowledge_space_{space}",
                    space_name=space,
                    top_k=4,
                    system_app=system_app,
                )
            )
        except Exception as e:
            logger.warning(f"load knowledge space {space} failed: {e}")
    return resources


def _make_kb_file_tools(space_names: List[str], system_app: Any) -> List[Any]:
    """Build the kb_xxx tool family scoped to the selected spaces.

    ``knowledge_retrieve`` only does semantic chunk retrieval — it cannot
    enumerate or read whole documents. The kb family covers the rest: list
    (kb_ls), find by name (kb_glob), grep contents (kb_grep), read a file
    (kb_cat) and semantic search. When several spaces are selected the tools
    take an optional ``space`` parameter restricted to the selection; wiki
    tools are added only when a single wiki-enabled space is selected.
    """
    if not space_names:
        return []
    from dbgpt.agent.resource.tool.base import tool

    kb_list = ", ".join(space_names)

    async def _impl(name: str, space: str, **kwargs):
        if name == "kb_ls":
            from dbgpt_serve.rag.tools.kb_file_tools import kb_ls as fn

            return await fn(knowledge_id=space, path=kwargs.get("path", ""))
        if name == "kb_glob":
            from dbgpt_serve.rag.tools.kb_file_tools import kb_glob as fn

            return await fn(knowledge_id=space, pattern=kwargs.get("pattern", ""))
        if name == "kb_grep":
            from dbgpt_serve.rag.tools.kb_file_tools import kb_grep as fn

            return await fn(
                knowledge_id=space,
                query=kwargs.get("query", ""),
                path=kwargs.get("path", ""),
                file_pattern=kwargs.get("file_pattern", ""),
            )
        if name == "kb_cat":
            from dbgpt_serve.rag.tools.kb_file_tools import kb_cat as fn

            return await fn(
                knowledge_id=space,
                path=kwargs.get("path", ""),
                start_line=kwargs.get("start_line", 1),
                end_line=kwargs.get("end_line", 0),
            )
        if name == "semantic_search":
            from dbgpt_serve.rag.tools.semantic_search_tool import (
                kb_semantic_search as fn,
            )

            return await fn(
                knowledge_id=space,
                query=kwargs.get("query", ""),
                top_k=kwargs.get("top_k", 5),
            )
        raise ValueError(f"unknown kb tool {name}")

    def _check_space(space: Optional[str]) -> str:
        if not space:
            if len(space_names) > 1:
                # No silent default with multiple spaces: a default that
                # silently picks the first space is indistinguishable from
                # "the space param does nothing" to the model.
                raise ValueError(
                    f"存在多个可用知识库,请显式指定 space 参数(可选: {kb_list})"
                )
            return space_names[0]
        if space not in space_names:
            raise ValueError(f"知识库 '{space}' 不在本节点可用范围: {kb_list}")
        return space

    async def _safe(name: str, space: Optional[str], **kwargs) -> str:
        try:
            return await _impl(name, _check_space(space), **kwargs)
        except Exception as e:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": f"{name} 失败: {e}"}]},
                ensure_ascii=False,
            )

    @tool(
        "kb_ls",
        description=(
            "列出知识库中的文件与目录,用于回答「有哪些文档」类问题。"
            f"可用知识库: {kb_list}。"
            '参数: {"path": "目录路径(可选)", "space": "知识库名(可选)"}'
        ),
    )
    async def _kb_ls(path: str = "", space: Optional[str] = None) -> str:
        return await _safe("kb_ls", space, path=path)

    @tool(
        "kb_glob",
        description=(
            "按文件名或 glob 模式查找知识库文件。"
            f"可用知识库: {kb_list}。"
            '参数: {"pattern": "文件名关键字或 glob", "space": "知识库名(可选)"}'
        ),
    )
    async def _kb_glob(pattern: str, space: Optional[str] = None) -> str:
        return await _safe("kb_glob", space, pattern=pattern)

    @tool(
        "kb_grep",
        description=(
            "按关键字搜索知识库文件内容,精确匹配优先于语义检索。"
            f"可用知识库: {kb_list}。"
            '参数: {"query": "关键字", "path": "目录过滤(可选)", '
            '"file_pattern": "文件模式(可选)", "space": "知识库名(可选)"}'
        ),
    )
    async def _kb_grep(
        query: str,
        path: str = "",
        file_pattern: str = "",
        space: Optional[str] = None,
    ) -> str:
        return await _safe(
            "kb_grep", space, query=query, path=path, file_pattern=file_pattern
        )

    @tool(
        "kb_cat",
        description=(
            "读取知识库中指定文件的内容(配合 kb_ls / kb_glob 使用)。"
            f"可用知识库: {kb_list}。"
            '参数: {"path": "文件路径", "start_line": "起始行(可选)", '
            '"end_line": "结束行(可选,0=到末尾)", "space": "知识库名(可选)"}'
        ),
    )
    async def _kb_cat(
        path: str,
        start_line: int = 1,
        end_line: int = 0,
        space: Optional[str] = None,
    ) -> str:
        return await _safe(
            "kb_cat", space, path=path, start_line=start_line, end_line=end_line
        )

    @tool(
        "semantic_search",
        description=(
            "按语义检索知识库内容片段;「有哪些文档」类问题请先用 kb_ls/kb_grep。"
            f"可用知识库: {kb_list}。"
            '参数: {"query": "自然语言查询", "top_k": "结果数(可选,默认5)", '
            '"space": "知识库名(可选)"}'
        ),
    )
    async def _semantic_search(
        query: str, top_k: int = 5, space: Optional[str] = None
    ) -> str:
        return await _safe("semantic_search", space, query=query, top_k=top_k)

    tools = [_kb_ls, _kb_glob, _kb_grep, _kb_cat, _semantic_search]

    # Wiki tools are bound per space; only attach for a single wiki-enabled
    # space (multi-space name collisions would be ambiguous).
    if len(space_names) == 1:
        try:
            from ..openapi.api_v1.tools.kb_tools import (
                _make_kb_wiki_tools,
                _wiki_enabled,
            )

            if _wiki_enabled(space_names[0]):
                tools.extend(_make_kb_wiki_tools(space_names[0]))
        except Exception as e:
            logger.warning(f"load wiki tools for {space_names[0]} failed: {e}")
    return tools


async def _load_mcp_tools(mcp_specs: List[str]) -> List[Any]:
    """Build MCP tool packs from inline specs (``sse:<url>`` / ``http:<url>``).

    Best-effort: a failing server is skipped with a warning rather than
    breaking the node.
    """
    tools: List[Any] = []
    for spec in mcp_specs or []:
        spec = (spec or "").strip()
        if not spec:
            continue
        transport, _, url = spec.partition(":")
        if transport not in ("sse", "http") or not url:
            logger.warning(f"invalid mcp spec skipped: {spec}")
            continue
        try:
            from dbgpt.agent.resource.tool.pack import MCPToolPack

            pack = MCPToolPack(
                url,
                transport="sse" if transport == "sse" else "streamable_http",
            )
            await pack.preload_resource()
            tools.extend(pack.sub_resources)
        except Exception as e:
            logger.warning(f"mcp server {url} preload failed, skipped: {e}")
    return tools


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_react_agent(
    *,
    goal: str,
    question: str,
    upstream_sections: Optional[List[UpstreamSection]] = None,
    profile_id: Optional[str] = None,
    tools: Optional[List[str]] = None,
    skills: Optional[List[str]] = None,
    datasources: Optional[List[str]] = None,
    knowledge: Optional[List[str]] = None,
    mcp: Optional[List[str]] = None,
    model: Optional[str] = None,
    max_turns: int = 10,
    llm_client: Any = None,
    system_app: Any = None,
    on_step: Optional[StepCallback] = None,
    on_artifact: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    conv_id: Optional[str] = None,
    language: Optional[str] = None,
    max_new_tokens: int = 16384,
) -> str:
    """Run one focused ReAct agent task and return the final answer text.

    Args:
        goal: The node's objective (from its config).
        question: The end-user's original question.
        upstream_sections: ``(label, kind, content)`` outputs of prior nodes.
        profile_id: Builtin profile id (see :data:`_PROFILES`).
        tools: Selected builtin tool ids (subset of SELECTABLE_TOOLS).
        skills: Selected skill package names.
        datasources: Selected datasource names (scopes sql_query).
        knowledge: Selected knowledge space names (scopes knowledge_retrieve).
        mcp: Inline MCP specs (``sse:<url>`` / ``http:<url>``).
        model: LLM model name; None = default model.
        max_turns: ReAct loop cap (1-30).
        llm_client: The LLMClient to use (required).
        system_app: The SystemApp (defaults to CFG.SYSTEM_APP).
        on_step: Async callback receiving :class:`AgentStepEvent` per round.
        conv_id: Isolation anchor; auto-generated when absent.
        language: ``zh`` or ``en`` (defaults to CFG.LANGUAGE).
        max_new_tokens: Model output cap for this node (HTML report tool
            args need far more than the agent default of 4096).

    Returns:
        The agent's final answer text.
    """
    from dbgpt.agent import AgentContext, AgentMemory, AgentMessage
    from dbgpt.agent.core.memory.gpts import DefaultGptsPlansMemory, GptsMemory
    from dbgpt.agent.expand.actions.react_action import Terminate
    from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
    from dbgpt.core import PromptTemplate
    from dbgpt_serve.agent.agents.db_gpts_memory import MetaDbGptsMessageMemory

    from ..openapi.api_v1.subagent.react_tools import make_react_tools

    system_app = system_app or CFG.SYSTEM_APP
    zh = (language or getattr(CFG, "LANGUAGE", "zh") or "zh").startswith("zh")
    profile = get_agent_profile(profile_id)
    selected_tools = [t for t in (tools or []) if t in SELECTABLE_TOOLS]
    selected_skills = [s for s in (skills or []) if s]
    datasources = [d for d in (datasources or []) if d]
    knowledge = [k for k in (knowledge or []) if k]
    max_turns = max(1, min(int(max_turns or 10), 30))
    conv_id = conv_id or f"taskflow_agent_{uuid.uuid4().hex[:12]}"

    # ---- tools ----------------------------------------------------------
    react_state: Dict[str, Any] = {"conv_id": conv_id, "file_path": None}
    if datasources:
        # Carried into query artifacts so the edit & re-run endpoint can
        # re-resolve the connector for flow-produced artifacts as well.
        react_state["database_name"] = datasources[0]
    knowledge_resources = _load_knowledge_resources(knowledge, system_app)
    single_connector = None
    if len(datasources) == 1:
        try:
            from dbgpt_serve.datasource.manages import ConnectorManager

            manager = ConnectorManager.get_instance(system_app)
            single_connector = manager.get_connector(datasources[0])
        except Exception as e:
            logger.warning(f"load connector {datasources[0]} failed: {e}")

    factory = make_react_tools(
        react_state,
        database_connector=single_connector,
        knowledge_resources=knowledge_resources,
    )
    tool_list: List[Any] = []
    for name in selected_tools:
        if name == "sql_query" and datasources:
            if len(datasources) > 1 or single_connector is None:
                tool_list.append(_make_multi_db_sql_tool(datasources, system_app))
            else:
                tool_list.append(factory["sql_query"])
        elif name == "knowledge_retrieve" and knowledge_resources:
            tool_list.append(factory["knowledge_retrieve"])
            # Semantic retrieval alone cannot enumerate/read documents — attach
            # the kb_xxx family (ls / glob / grep / cat / semantic_search[,
            # wiki]) scoped to the selected spaces.
            tool_list.extend(_make_kb_file_tools(knowledge, system_app))
        elif name in factory and name not in ("sql_query", "knowledge_retrieve"):
            tool_list.append(factory[name])
    if selected_skills:
        for name in SKILL_TOOLS:
            if name in factory:
                tool_list.append(factory[name])
    tool_list.extend(await _load_mcp_tools(mcp or []))
    tool_list.append(Terminate())
    tool_pack = ToolPack(tool_list)

    # ---- prompt ---------------------------------------------------------
    persona = (_PROFILE_PROMPT_ZH if zh else _PROFILE_PROMPT_EN)[profile.profile_id]
    template = _SYSTEM_TEMPLATE_ZH if zh else _SYSTEM_TEMPLATE_EN
    system_text = template.format(
        persona=persona,
        skills_section=_build_skills_section(selected_skills, zh),
        resources_section=_build_resources_section(datasources, knowledge, zh),
    )
    prompt = PromptTemplate(
        template=system_text, input_variables=[], template_format="jinja2"
    )

    # ---- memory / context ----------------------------------------------
    gpts_memory = GptsMemory(
        plans_memory=DefaultGptsPlansMemory(),
        message_memory=MetaDbGptsMessageMemory(),
    )
    gpts_memory.init(conv_id, enable_vis_message=False)
    agent_memory = AgentMemory(gpts_memory=gpts_memory)

    if model:
        llm_config = LLMConfig(
            llm_client=llm_client,
            llm_strategy=LLMStrategyType.Priority,
            strategy_context=json.dumps([model]),
        )
    else:
        llm_config = LLMConfig(llm_client=llm_client)
    context = AgentContext(
        conv_id=conv_id,
        gpts_app_code="taskflow_agent_node",
        gpts_app_name=f"TaskFlow-{profile.label_en}",
        language="zh" if zh else "en",
        # HTML report tool args can run to 8-12k tokens; the 4096 default
        # truncated them mid-string and every render failed empty.
        max_new_tokens=max_new_tokens,
        enable_context_management=True,
        enable_native_function_calling=True,
    )

    agent = await (
        ToolCallingReActAgent(max_retry_count=max_turns)
        .bind(context)
        .bind(agent_memory)
        .bind(llm_config)
        .bind(tool_pack)
        .bind(prompt)
        .build()
    )

    # ---- step event bridge ----------------------------------------------
    async def _callback(event_type: str, payload: dict) -> None:
        if not on_step:
            return
        try:
            round_num = int(payload.get("round") or 0)
            if event_type == "thinking":
                reply = _clean_thought_text(payload.get("llm_reply") or "")
                if reply:
                    await on_step(
                        AgentStepEvent(
                            kind="thinking",
                            title="思考" if zh else "Thinking",
                            detail=reply[:400],
                            round=round_num,
                        )
                    )
                return
            if event_type != "act":
                return
            ao = payload.get("action_output") or {}
            if ao.get("terminate"):
                return
            action = ao.get("action")
            if not action or action.lower() == "terminate":
                return
            action_input = ao.get("action_input")
            detail = (
                json.dumps(action_input, ensure_ascii=False)
                if not isinstance(action_input, str)
                else action_input
            )
            await on_step(
                AgentStepEvent(
                    kind="action",
                    title=str(action),
                    detail=(detail or "")[:400],
                    round=round_num,
                )
            )
            obs = ao.get("observations") or ao.get("content") or ""
            if obs:
                await on_step(
                    AgentStepEvent(
                        kind="observation",
                        title="观察" if zh else "Observation",
                        detail=str(obs)[:400],
                        round=round_num,
                    )
                )
            # First-class artifacts (html reports, query result sets) are
            # captured in full — the trace row above only keeps a 400-char
            # preview.
            if on_artifact and str(action) in ("html_interpreter", "sql_query") and obs:
                try:
                    env = json.loads(obs) if isinstance(obs, str) else None
                    env_chunks = env.get("chunks") if isinstance(env, dict) else None
                    if isinstance(env_chunks, list):
                        for chunk in env_chunks:
                            if not isinstance(chunk, dict) or not chunk.get("content"):
                                continue
                            if (
                                str(action) == "html_interpreter"
                                and chunk.get("output_type") == "html"
                            ):
                                await on_artifact(
                                    {
                                        "type": "html",
                                        "title": str(chunk.get("title") or "report"),
                                        "content": chunk.get("content"),
                                    }
                                )
                            elif (
                                str(action) == "sql_query"
                                and chunk.get("output_type") == "query"
                            ):
                                await on_artifact(
                                    {
                                        "type": "query",
                                        "content": chunk.get("content"),
                                    }
                                )
                except Exception:
                    # Artifact capture is best-effort; never break the loop.
                    pass
        except Exception:
            # Step events are best-effort; never break the agent loop.
            pass

    user_message = build_user_message(goal, question, upstream_sections or [])
    reply = await agent.generate_reply(
        received_message=AgentMessage(content=user_message),
        sender=agent,
        stream_callback=_callback,
    )
    content = ""
    if reply is not None:
        # Prefer the terminate action's report; unwrap the ReAct envelope
        # (Thought:/Action:/Action Input) so the returned answer is clean
        # user-facing text, not protocol noise.
        action_report = getattr(reply, "action_report", None)
        raw = (
            action_report.content
            if action_report is not None and getattr(action_report, "content", None)
            else getattr(reply, "content", "") or ""
        )
        content = _robust_final_answer(raw if isinstance(raw, str) else str(raw))
        # Safety net: a terminate result that is still a raw tool envelope
        # ({"chunks": ...}) must never reach the answer area as JSON noise.
        readable = _envelope_readable(content, zh)
        if readable:
            content = readable
    if on_step:
        try:
            await on_step(
                AgentStepEvent(
                    kind="answer",
                    title="回答" if zh else "Answer",
                    detail=content[:400],
                    round=max_turns,
                )
            )
        except Exception:
            pass
    return content.strip()
