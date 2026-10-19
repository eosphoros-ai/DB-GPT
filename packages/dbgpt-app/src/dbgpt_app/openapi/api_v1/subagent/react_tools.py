"""ReAct tool factory for the react-agent link.

Builds the set of ReAct tools that are bound to a per-(sub-)agent
``react_state`` dict. The main agent and every sub-agent each call
``make_react_tools`` once, capturing their own ``react_state`` — this is the
physical prerequisite for per-sub-agent state isolation (see design spec
§4.5 / plan stage 1).

SQL, Python, skill execution, shell execution and HTML rendering use the shared tool
factories. Each factory captures this agent's state so fixes apply to both the
main agent and sub-agents without sharing their mutable session state.

Returns 8 tools::

    load_skill / load_tools / knowledge_retrieve / sql_query /
    code_interpreter / shell_interpreter / execute_skill_script_file /
    html_interpreter

``todowrite`` is intentionally NOT here — it shares ``_todo_list`` with the
SSE main loop and stays in ``_react_agent_stream``. The module-level skill
tools (``execute_skill_script`` / ``get_skill_resource``) are imported
directly by callers, not rebuilt here.
"""

import json
import logging
from typing import Any, Dict

from dbgpt._private.config import Config
from dbgpt.agent.resource.base import AgentResource, ResourceType
from dbgpt.agent.resource.manage import get_resource_manager
from dbgpt.agent.resource.tool.base import tool
from dbgpt.configs.model_config import SKILLS_DIR
from dbgpt.core.interface.report_capture import get_current_artifact_sink

from ..tools.code_interpreter import (
    make_code_interpreter as make_shared_code_interpreter,
)
from ..tools.html_interpreter import make_html_interpreter
from ..tools.knowledge_retrieve import (
    make_knowledge_retrieve as make_shared_knowledge_retrieve,
)
from ..tools.shell_interpreter import make_shell_interpreter
from ..tools.skill_tools import make_execute_skill_script_file
from ..tools.sql_query import make_sql_query as make_shared_sql_query

CFG = Config()
logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = SKILLS_DIR


def make_react_tools(
    react_state: dict,
    *,
    database_connector: Any = None,
    knowledge_resources: Any = None,
) -> Dict[str, Any]:
    """Build a set of ReAct tools bound to the given ``react_state``.

    Each call returns a brand-new set of closure tools that capture the
    passed-in ``react_state``. The main agent and every sub-agent call this
    once, achieving state isolation.

    Args:
        react_state: The per-agent mutable state container. The only
            per-sub-agent isolation anchor. Tools read/write ``conv_id``,
            ``file_path``, ``generated_images``, ``image_url_map``,
            ``auto_data``, ``matched``, ``skill_prompt``.
        database_connector: Shared read-only DB connector (or None). Used by
            ``sql_query``.
        knowledge_resources: Shared read-only knowledge resources (or None).
            Used by ``knowledge_retrieve``.

    Returns:
        A dict mapping tool name -> tool callable, with 8 entries:
        ``load_skill``, ``load_tools``, ``knowledge_retrieve``, ``sql_query``,
        ``code_interpreter``, ``shell_interpreter``,
        ``execute_skill_script_file``, ``html_interpreter``.
    """

    @tool(
        description="Load skill content by skill name and file path. "
        "Returns the SKILL.md content of the specified skill. "
        '参数: {"skill_name": "技能名称", "file_path": "技能文件路径"}'
    )
    def load_skill(skill_name: str, file_path: str) -> str:
        """Load the skill content (SKILL.md) by skill name and file path.

        Args:
            skill_name: The name of the skill to load.
            file_path: The file path of the skill.
        """
        from dbgpt.agent.claude_skill import get_registry

        # Try to get skill from registry
        registry = get_registry()
        matched = registry.get_skill(skill_name)

        # If not found, try case-insensitive match
        if not matched:
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    matched = registry.get_skill(s.name)
                    break

        if not matched:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Skill '{skill_name}' not found",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Update react_state for compatibility with existing logic
        react_state["matched"] = matched
        react_state["skill_prompt"] = matched.get_prompt()

        # Build response content
        chunks = [
            {
                "output_type": "text",
                "content": f"Skill: {matched.metadata.name}",
            },
            {
                "output_type": "text",
                "content": f"File path: {file_path}",
            },
            {"output_type": "text", "content": "---"},
        ]

        # Add skill content/prompt
        if matched.instructions:
            chunks.append({"output_type": "markdown", "content": matched.instructions})
        elif matched.prompt_template:
            prompt_text = (
                matched.prompt_template.template
                if hasattr(matched.prompt_template, "template")
                else str(matched.prompt_template)
            )
            chunks.append({"output_type": "markdown", "content": prompt_text})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Resolve required tools for the selected skill.")
    def load_tools() -> str:
        matched = react_state.get("matched")
        rm = get_resource_manager(CFG.SYSTEM_APP)
        required_tools = matched.metadata.required_tools if matched else []
        if not required_tools:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No required tools specified",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        loaded = []
        failed = []
        for tool_name in required_tools:
            try:
                rm.build_resource_by_type(
                    ResourceType.Tool.value,
                    AgentResource(type=ResourceType.Tool.value, value=tool_name),
                )
                loaded.append(tool_name)
            except Exception as e:
                failed.append(f"{tool_name} ({e})")
        chunks = []
        if loaded:
            chunks.append(
                {"output_type": "text", "content": f"Loaded: {', '.join(loaded)}"}
            )
        if failed:
            chunks.append(
                {"output_type": "text", "content": f"Failed: {', '.join(failed)}"}
            )
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="Retrieve relevant information from the knowledge base. "
        "Use this tool when the user question involves content that may be "
        'in the knowledge base. Parameters: {{"query": "search query"}}'
    )
    async def legacy_knowledge_retrieve(query: str) -> str:
        if not knowledge_resources:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No knowledge base available",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        resource = knowledge_resources[0]
        try:
            chunks = await resource.retrieve(query)
            if chunks:
                content = "\n".join(
                    [f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks[:5])]
                )
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Retrieved {len(chunks)} relevant documents"
                                ),
                            },
                            {"output_type": "markdown", "content": content},
                        ]
                    },
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": "No relevant information found",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Knowledge retrieval failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description=(
            "对用户选择的数据库执行 SQL 查询（仅支持 SELECT）。"
            '参数: {"sql": "SELECT 语句"}'
        )
    )
    def sql_query(sql: str) -> str:
        """Execute a read-only SQL query against the selected database."""
        if database_connector is None:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper().lstrip()
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
        ]
        for kw in forbidden:
            if sql_upper.startswith(kw):
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"安全限制: 不允许执行 {kw} 语句，"
                                    f"仅支持 SELECT 查询。"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            result = database_connector.run(sql_stripped)
            if not result:
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ]
                    },
                    ensure_ascii=False,
                )

            # result[0] = column names, result[1:] = data rows
            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = result[1:]

            # Build markdown table
            header = "| " + " | ".join(col_names) + " |"
            separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
            md_rows = []
            for row in rows[:50]:
                md_rows.append("| " + " | ".join(str(v) for v in row) + " |")
            table = "\n".join([header, separator] + md_rows)
            if len(rows) > 50:
                table += f"\n\n（仅显示前 50 行，共 {len(rows)} 行）"

            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"SQL 执行失败: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    # SQL/Python are semantic execution boundaries. Delegate them to the same
    # implementations used by the main agent so capture, safety, truncation,
    # and future fixes cannot diverge between parent and child agents.
    shared_sql_query = make_shared_sql_query(
        react_state,
        database_connector,
        max_output_chars=None,
    )
    shared_code_interpreter = make_shared_code_interpreter(
        react_state,
        max_output_chars=2_000,
        legacy_truncation_notice=True,
    )
    shared_knowledge_retrieve = make_shared_knowledge_retrieve(
        react_state, knowledge_resources or []
    )

    @tool(
        description="Retrieve relevant information from the knowledge base. "
        "Use this tool when the user question involves content that may be "
        'in the knowledge base. Parameters: {{"query": "search query"}}'
    )
    async def knowledge_retrieve(query: str) -> str:
        if get_current_artifact_sink() is None:
            return await legacy_knowledge_retrieve(query=query)
        return await shared_knowledge_retrieve(query=query)

    return {
        "load_skill": load_skill,
        "load_tools": load_tools,
        "knowledge_retrieve": knowledge_retrieve,
        "sql_query": shared_sql_query,
        "code_interpreter": shared_code_interpreter,
        "shell_interpreter": make_shell_interpreter(react_state),
        "execute_skill_script_file": make_execute_skill_script_file(react_state),
        "html_interpreter": make_html_interpreter(react_state, DEFAULT_SKILLS_DIR),
    }
