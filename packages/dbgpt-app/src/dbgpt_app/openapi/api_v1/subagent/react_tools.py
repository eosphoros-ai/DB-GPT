"""ReAct tool factory for the react-agent link.

Builds the set of ReAct tools that are bound to a per-(sub-)agent
``react_state`` dict. The main agent and every sub-agent each call
``make_react_tools`` once, capturing their own ``react_state`` — this is the
physical prerequisite for per-sub-agent state isolation (see design spec
§4.5 / plan stage 1).

These tool bodies were relocated verbatim from ``agentic_data_api.py``; only
their dependency sources changed (closure free variables -> factory params or
module-level imports). Behavior is identical, so existing conversations
regress identically.

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
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dbgpt._private.config import Config
from dbgpt.agent.resource.base import AgentResource, ResourceType
from dbgpt.agent.resource.manage import get_resource_manager
from dbgpt.agent.resource.tool.base import tool
from dbgpt.configs.model_config import SKILLS_DIR
from dbgpt_app.openapi.api_v1.template_renderer import render_template_placeholders

CFG = Config()
logger = logging.getLogger(__name__)

DEFAULT_SKILLS_DIR = SKILLS_DIR
AUTO_DATA_MARKER_PATTERN = re.compile(
    r"###([A-Z0-9_]+)_START###\s*(.*?)\s*###\1_END###", re.DOTALL
)


def _extract_auto_data_markers(text: str) -> tuple[str, Dict[str, str]]:
    """Extract generic marker blocks from script output text.

    Marker format:
        ###KEY_START###...###KEY_END###
    """

    if not text or "###" not in text:
        return text, {}

    extracted: Dict[str, str] = {}

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = match.group(2).strip()
        if value:
            extracted[key] = value
        return ""

    cleaned = AUTO_DATA_MARKER_PATTERN.sub(_replace, text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, extracted


def _try_repair_truncated_code(raw_code: str) -> Optional[str]:
    """Attempt to fix code that was truncated by the LLM's token limit.

    Common symptoms: unterminated string literals, unclosed brackets/parens.
    Strategy:
      1. Remove the last (likely incomplete) logical line.
      2. Close any remaining open brackets / parentheses.
      3. Re-compile. If it passes, return the repaired code.
    Returns None if repair is not possible.
    """

    lines = raw_code.split("\n")
    # Try progressively removing trailing lines (up to 10) to find a
    # clean cut-off point.
    for trim in range(1, min(11, len(lines))):
        candidate_lines = lines[: len(lines) - trim]
        if not candidate_lines:
            continue
        candidate = "\n".join(candidate_lines)

        # Strip any trailing incomplete string by trying to tokenize
        # and removing broken tail tokens.
        # Close unmatched brackets/parens/braces
        open_chars = {"(": ")", "[": "]", "{": "}"}
        close_chars = set(open_chars.values())
        stack: list = []
        for ch in candidate:
            if ch in open_chars:
                stack.append(open_chars[ch])
            elif ch in close_chars:
                if stack and stack[-1] == ch:
                    stack.pop()

        # Append closing chars in reverse order
        if stack:
            candidate += "\n" + "".join(reversed(stack))

        try:
            compile(candidate, "<repair>", "exec")
            return candidate
        except SyntaxError:
            continue
    return None


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
            ``auto_data``, ``ratio_data``, ``matched``, ``skill_prompt``.
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
    async def knowledge_retrieve(query: str) -> str:
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

    @tool(
        description="Execute Python code for data analysis and computation. "
        "Supports pandas, numpy, matplotlib, json, os, etc. "
        "Use this tool when you need to run Python code to process data, "
        "generate charts, or perform calculations. "
        'Parameters: {{"code": "python code string"}}'
    )
    async def code_interpreter(code: str) -> str:
        """Execute arbitrary Python code and return stdout/stderr.

        Runs in a subprocess using the project's Python interpreter,
        so all installed packages (pandas, numpy, etc.) are available.
        CRITICAL: Each call is completely independent — variables do NOT
        persist between calls. Every code snippet MUST include all necessary
        data loading (e.g. df = pd.read_csv(FILE_PATH)) and processing.
        Never assume df or any other variable already exists.
        Always print() results you want to see in the output.
        """
        import asyncio
        import shutil
        import sys
        import uuid

        from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH

        if not code or not code.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No code provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Use persistent work dir under pilot/tmp/{conv_id} so files
        # survive across calls and can be referenced later (e.g. in HTML).
        cid = react_state.get("conv_id") or "default"
        work_dir = os.path.join(PILOT_PATH, "tmp", cid)
        os.makedirs(work_dir, exist_ok=True)

        # Collect image files that existed BEFORE this run
        IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        pre_existing_images: set = set()
        for root, _dirs, files in os.walk(work_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    pre_existing_images.add(os.path.join(root, f))

        preamble_lines = [
            "import json",
            "import os",
            "import pandas as pd",
            "import numpy as np",
            f'PLOT_DIR = r"{work_dir}"',
            "os.makedirs(PLOT_DIR, exist_ok=True)",
        ]
        fp = react_state.get("file_path")
        if fp:
            preamble_lines.append(f'FILE_PATH = r"{fp}"')
        preamble = "\n".join(preamble_lines) + "\n"
        full_code = preamble + code

        try:
            compile(full_code, "<code_interpreter>", "exec")
        except SyntaxError as se:
            # Attempt auto-repair for truncated code (common with long LLM
            # outputs that hit the token limit).
            repaired = _try_repair_truncated_code(full_code)
            if repaired is not None:
                logger.warning(
                    "code_interpreter: auto-repaired truncated code "
                    f"(original SyntaxError: {se.msg} line {se.lineno})"
                )
                full_code = repaired
                # Strip the preamble back out for the "code" display chunk
                code = full_code[len(preamble) :]
            else:
                error_msg = (
                    f"SyntaxError before execution: {se.msg} "
                    f"(line {se.lineno})\n"
                    "Please regenerate complete, syntactically valid Python "
                    "code. Keep code under 80 lines and split long tasks "
                    "into multiple code_interpreter calls."
                )
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "code", "content": code.strip()},
                            {"output_type": "text", "content": error_msg},
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            tmp_path = os.path.join(work_dir, "_run.py")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                tmp.write(full_code)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output_text = stdout.decode("utf-8", errors="replace")
            error_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and error_text:
                output_text = (
                    output_text + "\n[ERROR]\n" + error_text
                    if output_text
                    else error_text
                )
        except asyncio.TimeoutError:
            output_text = "Execution timed out (60s limit)"
        except Exception as e:
            output_text = f"Execution error: {e}"

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            clean_output = output_text.strip()
            max_out_len = 2000
            if len(clean_output) > max_out_len:
                truncation_notice = (
                    f"\n\n... [Output truncated, length: {len(clean_output)} chars."
                    f" Only showing first {max_out_len} chars."
                    f" If you generated HTML, the file is saved.]"
                )
                clean_output = clean_output[:max_out_len] + truncation_notice
            chunks.append({"output_type": "text", "content": clean_output})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output — add print() to see results)",
                }
            )

        # Scan work_dir recursively for NEW image files generated by this run
        try:
            os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    full_path = os.path.join(root, fname)
                    if ext in IMAGE_EXTS and full_path not in pre_existing_images:
                        unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                        dest = os.path.join(STATIC_MESSAGE_IMG_PATH, unique_name)
                        shutil.copy2(full_path, dest)
                        img_url = f"/images/{unique_name}"
                        chunks.append(
                            {
                                "output_type": "image",
                                "content": img_url,
                            }
                        )
                        # Track generated images in react_state for
                        # html_interpreter to reference later
                        react_state.setdefault("generated_images", []).append(img_url)
        except Exception:
            pass

        # Clean up the temp script file but keep work_dir for persistence
        try:
            script_path = os.path.join(work_dir, "_run.py")
            if os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass

        # Append a summary of ALL generated images so far, so the LLM
        # has a clear reference when generating HTML later.
        all_images = react_state.get("generated_images", [])
        if all_images:
            img_summary = "已生成的图片URL（在生成HTML时请使用这些URL）:\n" + "\n".join(
                f"  - {url}" for url in all_images
            )
            chunks.append({"output_type": "text", "content": img_summary})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="Execute shell/bash commands in a sandboxed environment. "
        "Use this tool when you need to run shell commands such as ls, cat, "
        "grep, curl, apt, pip, git, or any other CLI tool. "
        "The sandbox provides resource limits (256MB memory, 30s timeout) "
        "and process isolation. "
        'Parameters: {"code": "shell command(s) to execute"}'
    )
    async def shell_interpreter(code: str) -> str:
        """Execute shell/bash commands in a sandboxed environment.

        Uses dbgpt-sandbox LocalRuntime to run bash scripts with:
        - Memory limit: 256MB
        - Timeout: 30 seconds
        - Process tree management (cleanup on timeout/error)
        - Security validation (blocks dangerous patterns like rm -rf /)
        Each call is independent — no state persists between calls.
        """
        import uuid

        if not code or not code.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No command provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            from dbgpt_sandbox.sandbox.execution_layer.base import (
                ExecutionStatus,
                SessionConfig,
            )
            from dbgpt_sandbox.sandbox.execution_layer.local_runtime import (
                LocalRuntime,
            )
        except ImportError:
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "code", "content": code.strip()},
                        {
                            "output_type": "text",
                            "content": (
                                "Error: dbgpt-sandbox package is not installed. "
                                "Please install it with: pip install dbgpt-sandbox"
                            ),
                        },
                    ]
                },
                ensure_ascii=False,
            )

        session_id = f"bash_{uuid.uuid4().hex[:12]}"
        runtime = LocalRuntime()

        # Align the shell working dir to pilot/tmp/{conv_id} (same as
        # code_interpreter and the image-scan dir below) so parallel
        # sub-agents do not collide in the project root. Previously this was
        # ROOT_PATH, which was inconsistent with the image-scan dir.
        from dbgpt.configs.model_config import PILOT_PATH

        cid = react_state.get("conv_id") or "default"
        sandbox_work_dir = os.path.join(PILOT_PATH, "tmp", cid)
        os.makedirs(sandbox_work_dir, exist_ok=True)

        config = SessionConfig(
            language="bash",
            working_dir=sandbox_work_dir,
            max_memory=256 * 1024 * 1024,  # 256MB
            timeout=30,
        )

        output_text = ""
        try:
            session = await runtime.create_session(session_id, config)
            result = await session.execute(code)

            if result.status == ExecutionStatus.SUCCESS:
                output_text = result.output or ""
            elif result.status == ExecutionStatus.TIMEOUT:
                output_text = f"Execution timed out ({config.timeout}s limit)"
            else:
                output_text = result.error or "Unknown execution error"
                if result.output:
                    output_text = result.output + "\n[ERROR]\n" + output_text
        except Exception as e:
            output_text = f"Sandbox execution error: {e}"
        finally:
            try:
                await runtime.destroy_session(session_id)
            except Exception:
                pass

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            chunks.append({"output_type": "text", "content": output_text.strip()})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output)",
                }
            )

        # ── Safety-net post-processing for skill script execution ──
        # If the LLM used shell_interpreter to run a skill script despite
        # the prompt requesting execute_skill_script_file, we still capture
        # critical side-effects (ratio_data, images) into react_state.
        _code_lower = code.strip().lower()
        _is_skill_script = "skills/" in _code_lower and ".py" in _code_lower
        if _is_skill_script and output_text.strip():
            import shutil

            from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

            # 1) Capture calculate_ratios.py output as ratio_data
            if "calculate_ratios" in _code_lower:
                try:
                    ratio_data = json.loads(output_text.strip())
                    if isinstance(ratio_data, dict):
                        react_state["ratio_data"] = ratio_data
                        logger.info(
                            "shell_interpreter: captured %d ratio_data keys",
                            len(ratio_data),
                        )
                except Exception:
                    pass

            # 2) Capture generate_charts.py output — look for image paths
            #    and copy them to static dir, same as execute_skill_script_file
            if "generate_charts" in _code_lower:
                try:
                    os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                    # Try to parse JSON output for image paths
                    try:
                        chart_output = json.loads(output_text.strip())
                        if isinstance(chart_output, dict):
                            # Might be {"charts": {...}} or flat dict
                            chart_map = chart_output.get("charts", chart_output)
                            for name, abs_path in chart_map.items():
                                if isinstance(abs_path, str) and os.path.isfile(
                                    abs_path
                                ):
                                    ext = os.path.splitext(abs_path)[1].lower()
                                    if ext in IMAGE_EXTS:
                                        unique_name = (
                                            f"{uuid.uuid4().hex[:8]}_"
                                            f"{os.path.basename(abs_path)}"
                                        )
                                        dest = os.path.join(
                                            STATIC_MESSAGE_IMG_PATH, unique_name
                                        )
                                        shutil.copy2(abs_path, dest)
                                        img_url = f"/images/{unique_name}"
                                        react_state.setdefault(
                                            "generated_images", []
                                        ).append(img_url)
                                        orig_stem = os.path.splitext(
                                            os.path.basename(abs_path)
                                        )[0].lower()
                                        react_state.setdefault("image_url_map", {})[
                                            orig_stem
                                        ] = img_url
                    except (json.JSONDecodeError, TypeError):
                        pass
                    # Also scan the output dir for any new .png files
                    cid = react_state.get("conv_id") or "default"
                    from dbgpt.configs.model_config import PILOT_PATH

                    out_dir = os.path.join(PILOT_PATH, "tmp", cid)
                    if os.path.isdir(out_dir):
                        for fname in os.listdir(out_dir):
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in IMAGE_EXTS:
                                abs_path = os.path.join(out_dir, fname)
                                orig_stem = os.path.splitext(fname)[0].lower()
                                if orig_stem not in react_state.get(
                                    "image_url_map", {}
                                ):
                                    unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                                    dest = os.path.join(
                                        STATIC_MESSAGE_IMG_PATH, unique_name
                                    )
                                    shutil.copy2(abs_path, dest)
                                    img_url = f"/images/{unique_name}"
                                    react_state.setdefault(
                                        "generated_images", []
                                    ).append(img_url)
                                    react_state.setdefault("image_url_map", {})[
                                        orig_stem
                                    ] = img_url
                    # Append image URL summary for LLM reference
                    all_images = react_state.get("generated_images", [])
                    if all_images:
                        img_summary = (
                            "已生成的图片URL（在生成HTML报告时请使用这些URL）:\n"
                            + "\n".join(f"  - {url}" for url in all_images)
                        )
                        chunks.append({"output_type": "text", "content": img_summary})
                    logger.info(
                        "shell_interpreter: captured %d images for skill script",
                        len(react_state.get("image_url_map", {})),
                    )
                except Exception as e:
                    logger.warning(
                        "shell_interpreter: image post-processing failed: %s", e
                    )

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="执行技能scripts目录下的脚本文件。参数: "
        '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
    )
    async def execute_skill_script_file(
        skill_name: str, script_file_name: str, args: Optional[dict] = None
    ) -> str:
        """Execute a script file from a skill's scripts directory.

        After execution, any new image files (.png, .jpg, etc.) generated
        by the script are automatically copied to the static images directory
        and their URLs are returned in the output chunks.
        """
        import shutil
        import uuid

        from dbgpt.agent.skill.manage import get_skill_manager
        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        try:
            from dbgpt.configs.model_config import PILOT_PATH

            sm = get_skill_manager(CFG.SYSTEM_APP)
            cid = react_state.get("conv_id") or "default"
            out_dir = os.path.join(PILOT_PATH, "tmp", cid)
            os.makedirs(out_dir, exist_ok=True)
            # Auto-inject the correct file path from react_state into args.
            # The LLM sometimes corrupts the uploaded file path (e.g. changing
            # 'dbgpt-app' to 'dbgpt_app'), so we override any file-path-like
            # keys in args with the known-good path from react_state.
            real_file_path = react_state.get("file_path")
            if real_file_path and args:
                _FILE_PATH_KEYS = {
                    "input_file",
                    "file_path",
                    "data_path",
                    "csv_path",
                    "excel_path",
                    "data_file",
                }
                for key in list(args.keys()):
                    if key in _FILE_PATH_KEYS:
                        args[key] = real_file_path
            result_str = await sm.execute_skill_script_file(
                skill_name,
                script_file_name,
                args or {},
                output_dir=out_dir,
            )

            # Read script source code and prepend as a 'code' chunk
            # so the frontend can display it in the left pane.
            try:
                _skill_path = sm._get_skill_path(skill_name)
                _sf = script_file_name.lstrip("/\\")
                if _sf.startswith("scripts/") or _sf.startswith("scripts\\"):
                    _sf = _sf[8:]
                _script_abs = os.path.join(_skill_path, "scripts", _sf)
                with open(_script_abs, "r", encoding="utf-8") as _f:
                    _script_source = _f.read()
            except Exception:
                _script_source = None

            # Post-process: copy image files to static dir and replace
            # absolute paths with /images/ URLs.
            try:
                result_obj = json.loads(result_str)
                chunks = result_obj.get("chunks", [])
                # Prepend script source code as a 'code' chunk
                if _script_source:
                    chunks.insert(
                        0,
                        {
                            "output_type": "code",
                            "content": _script_source,
                        },
                    )
                os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                for chunk in chunks:
                    if chunk.get("output_type") == "image":
                        abs_path = chunk["content"]
                        if os.path.isabs(abs_path) and os.path.isfile(abs_path):
                            ext = os.path.splitext(abs_path)[1].lower()
                            if ext in IMAGE_EXTS:
                                unique_name = (
                                    f"{uuid.uuid4().hex[:8]}_"
                                    f"{os.path.basename(abs_path)}"
                                )
                                dest = os.path.join(
                                    STATIC_MESSAGE_IMG_PATH, unique_name
                                )
                                shutil.copy2(abs_path, dest)
                                img_url = f"/images/{unique_name}"
                                chunk["content"] = img_url
                                react_state.setdefault("generated_images", []).append(
                                    img_url
                                )
                                # Also store a map: original filename (no ext)
                                # -> served URL for template placeholder
                                # resolution.
                                orig_stem = os.path.splitext(
                                    os.path.basename(abs_path)
                                )[0].lower()
                                react_state.setdefault("image_url_map", {})[
                                    orig_stem
                                ] = img_url

                # Append image URL summary for LLM reference
                all_images = react_state.get("generated_images", [])
                if all_images:
                    img_summary = (
                        "已生成的图片URL（在生成HTML报告时请使用这些URL）:\n"
                        + "\n".join(f"  - {url}" for url in all_images)
                    )
                    chunks.append({"output_type": "text", "content": img_summary})
                auto_data = react_state.get("auto_data")
                if not isinstance(auto_data, dict):
                    auto_data = {}
                    react_state["auto_data"] = auto_data
                filtered_chunks = []
                for chunk in chunks:
                    if chunk.get("output_type") != "text":
                        filtered_chunks.append(chunk)
                        continue
                    content = chunk.get("content") or ""
                    cleaned, extracted = _extract_auto_data_markers(content)
                    if extracted:
                        auto_data.update(extracted)
                        logger.info(
                            "execute_skill_script_file: captured auto_data keys=%s",
                            sorted(extracted.keys()),
                        )
                    if cleaned:
                        chunk["content"] = cleaned
                        filtered_chunks.append(chunk)
                    elif not extracted:
                        filtered_chunks.append(chunk)
                chunks = filtered_chunks

                # Compatibility path for existing financial-report skill.
                if script_file_name == "calculate_ratios.py":
                    for chunk in chunks:
                        if chunk.get("output_type") == "text":
                            try:
                                ratio_data = json.loads(chunk["content"])
                                react_state["ratio_data"] = ratio_data
                            except Exception:
                                pass
                return json.dumps({"chunks": chunks}, ensure_ascii=False)
            except (json.JSONDecodeError, KeyError):
                return result_str
        except Exception as e:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
                ensure_ascii=False,
            )

    @tool(
        description="将 HTML 渲染为可交互的网页报告，这是向用户展示网页报告的唯一方式。"
        "【一次性】一次调用即可把【完整】报告渲染出来；同一份报告【禁止】重复调用本工具，"
        "渲染成功后若目标已达成请直接 terminate。"
        "【默认用法】直接传入完整的 HTML 字符串："
        '{"html": "<html>...</html>", "title": "报告标题"}。'
        "你需要自己生成完整的 HTML 代码"
        "（包含 <!DOCTYPE html>、<html>、<head>、<body> 等），"
        "然后传给 html 参数即可。"
        "HTML 可以很长，没有长度限制，不需要分段传入；"
        "若报告含多部分内容，请合并进【同一份】HTML 一次性渲染，"
        "不要分多次生成多份报告。"
        "【禁止】不要用 code_interpreter 写 HTML 再 print，"
        "不要用 code_interpreter 把 HTML 写入文件再读取，"
        "直接把 HTML 传给本工具即可。"
        "【技能模式 - 仅在使用技能时可选】如果正在使用技能（skill），可以用模板模式："
        '{"template_path": "技能名/templates/模板.html", '
        '"data": {"KEY": "值"}, "title": "标题"}。'
        '也可以用文件模式：{"file_path": "/path/to/report.html"}'
    )
    async def html_interpreter(
        html: str = "",
        title: str = "Report",
        file_path: str = "",
        template_path: str = "",
        data: dict | str = None,
    ) -> str:
        """Render HTML as an interactive web report.

        Default usage: pass a complete HTML string via the `html` parameter.
        The HTML can be arbitrarily long — no length limit, no chunking needed.

        Skill template mode (optional): pass `template_path` (relative to skills
        dir) plus a `data` dict whose keys match {{PLACEHOLDER}} tokens in the
        template. The backend reads the template and performs all replacements.

        Legacy fallback: `file_path` reads HTML from a file on disk.
        """
        import re

        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        # ── Mode 1: template_path + data ──────────────────────────────
        if template_path and template_path.strip():
            tp = template_path.strip()
            skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
            target = (skills_dir / tp).resolve()
            # Security: must be under skills_dir
            try:
                target.relative_to(skills_dir)
            except ValueError:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Invalid template_path: {tp}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            if not target.is_file():
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Template not found: {tp}. "
                                    "This skill does not have HTML templates. "
                                    "Please retry by calling html_interpreter "
                                    "with the `html` parameter instead — "
                                    "generate the complete HTML report code "
                                    "yourself and pass it directly via "
                                    '{"html": "<html>...</html>", '
                                    '"title": "report title"}.'
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            try:
                raw_template = target.read_text(encoding="utf-8")
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading template: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            # Replace {{KEY}} placeholders with values from data dict
            # Sometimes the LLM passes data as a JSON string instead of a dict
            replacements = data
            if isinstance(replacements, str):
                try:
                    replacements = json.loads(replacements)
                except Exception as e:
                    logger.warning(
                        f"html_interpreter failed to parse string data as json: {e}"
                    )
                    # Attempt to fix truncated JSON by appending closing
                    # braces/quotes
                    try:
                        fixed = str(replacements).rstrip()
                        if not fixed.endswith("}"):
                            if fixed.endswith('"'):
                                fixed += "}"
                            else:
                                fixed += '"}'
                        replacements = json.loads(fixed)
                    except Exception:
                        replacements = {}
            if not isinstance(replacements, dict):
                replacements = {}
            auto_data = react_state.get("auto_data", {})
            if isinstance(auto_data, dict):
                replacements = {**auto_data, **replacements}

            # Merge LLM replacements with ratio_data from calculate_ratios.py
            ratio_data = react_state.get("ratio_data", {})
            if isinstance(ratio_data, dict):
                # auto_data / LLM data overwrites ratio_data if keys overlap
                merged = {**ratio_data, **replacements}
                replacements = merged

            # Auto-resolve CHART_* placeholders from generated images.
            # image_url_map: {
            #     "financial_overview": "/images/abc_financial_overview.png"
            # }
            # Template uses:
            #     {{CHART_FINANCIAL_OVERVIEW}}
            #     -> /images/abc_financial_overview.png
            image_url_map = react_state.get("image_url_map", {})
            if isinstance(image_url_map, dict):
                for stem, url in image_url_map.items():
                    chart_key = f"CHART_{stem.upper()}"
                    if chart_key not in replacements:
                        replacements[chart_key] = url

            html = render_template_placeholders(raw_template, replacements)
            if not title or title == "Report":
                title = target.stem
            logger.info(
                "html_interpreter: template=%s, %d placeholders replaced, "
                "html=%d chars",
                tp,
                len(replacements),
                len(html),
            )

        # ── Mode 2: file_path ─────────────────────────────────────────
        elif file_path and file_path.strip():
            fp = file_path.strip()
            if not os.path.isfile(fp):
                cid = react_state.get("conv_id") or "default"
                from dbgpt.configs.model_config import PILOT_PATH

                alt = os.path.join(PILOT_PATH, "data", cid, os.path.basename(fp))
                if os.path.isfile(alt):
                    fp = alt
                else:
                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": f"File not found: {file_path}",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    html = f.read()
                if not title or title == "Report":
                    title = os.path.splitext(os.path.basename(fp))[0]
                logger.info(
                    "html_interpreter: read %d chars from file %s",
                    len(html),
                    fp,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading file: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        # ── Mode 3: inline html ──────────────────────────────────────
        # Unescape literal \n sequences that LLM may produce.
        # IMPORTANT: Only apply this unescape when html was provided directly
        # (inline mode).  Template mode (Mode 1) and file mode (Mode 2) produce
        # real HTML that already contains actual newlines and may contain JS
        # regex literals like /\\n/ which must NOT be collapsed into real
        # newlines — doing so corrupts the JS and breaks chart rendering.
        if html and isinstance(html, str) and not template_path and not file_path:
            if "\\n" in html:
                html = html.replace("\\n", "\n")
            if "\\t" in html:
                html = html.replace("\\t", "\t")
        if not html or not html.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No HTML content provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Post-process: fix image URLs that the LLM may have guessed wrong.
        # Files in STATIC_MESSAGE_IMG_PATH are named "{uuid8}_{original}.ext".
        # The LLM might reference "/images/original.ext" (without UUID prefix)
        # or even just "original.ext".  Build a lookup and replace.
        fixed_html = html.strip()
        try:
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
            # Map: lowercase base name (without uuid prefix) -> served path
            # e.g. "monthly_sales_trend.png"
            #      -> "/images/a1b2c3ff_monthly_sales_trend.png"
            name_to_served: Dict[str, str] = {}
            if os.path.isdir(STATIC_MESSAGE_IMG_PATH):
                for fname in os.listdir(STATIC_MESSAGE_IMG_PATH):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IMAGE_EXTS:
                        continue
                    # Strip the 8-char hex UUID prefix + underscore
                    # Pattern: <8 hex chars>_<original_name>
                    m = re.match(r"^[0-9a-f]{8}_(.+)$", fname, re.IGNORECASE)
                    if m:
                        base_name = m.group(1).lower()
                        served_path = f"/images/{fname}"
                        # Keep the latest (last alphabetically = most recent
                        # UUID)
                        name_to_served[base_name] = served_path

            if name_to_served:
                # Replace patterns like:
                #   src="/images/monthly_sales_trend.png"
                #   src="images/monthly_sales_trend.png"
                #   src="monthly_sales_trend.png"
                # with the correct served path.
                def _fix_img_src(match: re.Match) -> str:
                    prefix = match.group(1)  # src=" or src='
                    raw_path = match.group(2)  # the path value
                    quote = match.group(3)  # closing quote

                    # Extract just the filename from the path
                    filename = raw_path.rsplit("/", 1)[-1].lower()

                    # Check if it's already a correct served path
                    if re.match(r"^[0-9a-f]{8}_.+$", filename, re.IGNORECASE):
                        return match.group(0)  # Already has UUID prefix

                    if filename in name_to_served:
                        return f"{prefix}{name_to_served[filename]}{quote}"
                    return match.group(0)  # No match, keep original

                # Match src="..." or src='...' containing image references
                fixed_html = re.sub(
                    r"""(src\s*=\s*["'])"""
                    r"""([^"']+\.(?:png|jpg|jpeg|gif|svg|webp))"""
                    r"""(["'])""",
                    _fix_img_src,
                    fixed_html,
                    flags=re.IGNORECASE,
                )
        except Exception:
            pass  # If post-processing fails, use original HTML

        # Auto-append images generated during this session that the LLM
        # forgot to include in the HTML.
        try:
            gen_images = react_state.get("generated_images", [])
            if gen_images:
                # Extract all image filenames already referenced in the HTML
                # (e.g. "time_series_trend.png" from any src="...time_series_trend.png")
                html_img_stems = set(
                    re.sub(r"^[0-9a-f]+_", "", os.path.basename(src))
                    for src in re.findall(
                        r'<img[^>]+src=["\']([^"\']+)["\']', fixed_html, re.IGNORECASE
                    )
                )

                # An image is "missing" only when neither its exact URL nor its
                # stem (filename with UUID prefix stripped) is already covered.
                def _img_stem(url):
                    return re.sub(r"^[0-9a-f]+_", "", os.path.basename(url))

                missing = [
                    url
                    for url in gen_images
                    if url not in fixed_html and _img_stem(url) not in html_img_stems
                ]
                if missing:
                    imgs_html = "".join(
                        f'<div style="margin:16px 0">'
                        f'<img src="{url}" '
                        f'style="max-width:100%;height:auto;'
                        f'border-radius:8px">'
                        f"</div>"
                        for url in missing
                    )
                    section = (
                        '<div style="margin-top:32px">'
                        "<h2>📊 分析图表</h2>"
                        f"{imgs_html}</div>"
                    )
                    # Insert before </body> if present, otherwise append
                    if "</body>" in fixed_html.lower():
                        fixed_html = re.sub(
                            r"(</body>)",
                            section + r"\1",
                            fixed_html,
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        fixed_html += section
        except Exception:
            pass

        # A leading text chunk gives the ReAct LLM an explicit success signal.
        # Without it the observation is just the raw HTML source, which the model
        # cannot tell apart from "not done yet" and tends to re-render a second
        # report. The frontend ignores this text for rendering (the html chunk
        # below drives the report); it only steers the agent loop to terminate.
        chunks: List[Dict[str, Any]] = [
            {
                "output_type": "text",
                "content": (
                    "✅ HTML 报告已成功渲染并展示给用户。报告任务已完成，"
                    "请勿重复调用 html_interpreter 生成报告。"
                    "若全部目标已达成，请直接调用 terminate 结束。"
                ),
            },
            {"output_type": "html", "content": fixed_html, "title": title},
        ]
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return {
        "load_skill": load_skill,
        "load_tools": load_tools,
        "knowledge_retrieve": knowledge_retrieve,
        "sql_query": sql_query,
        "code_interpreter": code_interpreter,
        "shell_interpreter": shell_interpreter,
        "execute_skill_script_file": execute_skill_script_file,
        "html_interpreter": html_interpreter,
    }
