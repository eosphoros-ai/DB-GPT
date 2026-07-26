"""Sub-agent builder and parallel dispatch.

This module owns the parallel sub-agent delegation logic for the
``POST /v1/chat/react-agent`` link (design spec §4.3/§4.4, plan stages 2-4):

    build_sub_react_agent      construct an isolated child ReActAgent
    make_dispatch_tool         the ``dispatch_parallel_tasks`` tool factory
    DISPATCH_PROMPT_SECTION    the lead-agent delegation rubric (module const,
                               kept out of the oversized agentic_data_api.py)

Isolation model (spec §4.5):
    Each sub-agent gets its own conv_id (``{parent}__sub_{i}`` — drives the
    subprocess cwd ``pilot/tmp/{conv_id}``), its own ``react_state`` dict
    (artifact bookkeeping), and its own ``GptsMemory`` (not cached). Tools are
    rebuilt via ``make_react_tools`` capturing the sub-agent's own state.

Resource inheritance (定位 A, spec §4.5.1):
    Stateful resources (database_connector / knowledge_resources /
    connector MCP tools) are SHARED from the main agent, not rebuilt. MCP is
    concurrency-safe because each call opens a fresh session (pack.py). Only
    read-only MCP tools are injected — write tools are filtered out by the
    catalog's ``confirm_actions`` list.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.resource import ToolPack, tool
from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt.core import PromptTemplate

from .react_tools import make_react_tools
from .result import attach_agent_attribution, extract_subagent_result

logger = logging.getLogger(__name__)

# Sub-agent step budget — smaller than the main agent (30) to bound cost.
_SUBAGENT_MAX_RETRY = 15

# Per-sub-agent wall-clock timeout (seconds).
_SUBAGENT_TIMEOUT = 600

# Max chars of a sub-agent step observation forwarded to the frontend process
# view. Keeps SSE light; full artifacts still flow via subagent.artifacts.
_SUBAGENT_OBS_MAX_CHARS = 2000

# HTML report chunks must NOT be cut to the small text cap — a truncated HTML
# document is unclosed and renders blank/garbled in the iframe. They get a much
# larger guard (still bounded so a runaway document can't flood the SSE stream).
_SUBAGENT_HTML_MAX_CHARS = 200_000

# The overview card needs a useful final summary, not the full report payload.
# Full structured outputs still travel through agent.step / the dispatch result.
_SUBAGENT_RESULT_SUMMARY_MAX_CHARS = 8_000

# Matches the tool-result wrapper {"chunks": [...]} that DB-GPT tools return.
_CHUNKS_WRAPPER_RE = re.compile(r'\{\s*"chunks"\s*:\s*\[.*?\]\s*\}', re.DOTALL)


def _parse_observation_chunks(obs: Any) -> List[Dict[str, Any]]:
    """Parse a sub-agent step observation into structured display chunks.

    A single ReAct act may invoke several tools, so ``observations`` can be
    SEVERAL ``{"chunks":[{output_type,content}]}`` wrappers concatenated
    (sometimes with plain text between them). We extract every wrapper, unwrap
    its inner chunks, and keep any in-between text — returning a flat list of
    ``{"output_type","content"}`` ready for the frontend renderer (markdown
    tables / code / json / images), so the raw JSON string is NEVER shown
    verbatim.

    Image chunks are KEPT here (their ``content`` is a short ``/images/...``
    URL, not bytes) so the right-panel process view can inline-render them
    exactly like the main agent's ``OutputRenderer`` does. The same images
    also flow via ``subagent.artifacts`` for the files tab / preview / download.
    """
    if obs is None:
        return []
    if not isinstance(obs, str):
        obs = str(obs)
    text = obs.strip()
    if not text:
        return []

    out: List[Dict[str, Any]] = []
    last_end = 0
    matched_any = False
    for m in _CHUNKS_WRAPPER_RE.finditer(text):
        matched_any = True
        # Plain text sitting before this wrapper (e.g. a stray action label).
        gap = text[last_end : m.start()].strip()
        if gap:
            out.append({"output_type": "text", "content": gap})
        last_end = m.end()
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            out.append({"output_type": "text", "content": m.group(0)})
            continue
        for c in parsed.get("chunks", []) if isinstance(parsed, dict) else []:
            if not isinstance(c, dict):
                continue
            ot = c.get("output_type") or "text"
            content = c.get("content")
            if content is None:
                continue
            out.append({"output_type": ot, "content": content})
    # Trailing text after the last wrapper (or the whole thing if no wrapper).
    tail = text[last_end:].strip()
    if tail:
        out.append({"output_type": "text", "content": tail})
    # No wrapper at all => treat the whole observation as plain text.
    if not matched_any and not out:
        out.append({"output_type": "text", "content": text})
    return out


def _extract_sql_action_input(action_input: Any) -> Optional[str]:
    """Return the SQL query from a confirmed sql_query call.

    Only the SQL string is exposed to the frontend. Other tool arguments stay
    private so the sub-agent progress event cannot leak paths, HTML, or
    connector credentials.
    """
    parsed = action_input
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except (TypeError, ValueError):
            return None
    if not isinstance(parsed, dict):
        return None
    sql = parsed.get("sql")
    if not isinstance(sql, str):
        return None
    return sql.strip().rstrip(";").strip() or None


def _extract_sql_from_llm_reply(llm_reply: Any) -> Optional[str]:
    """Recover a confirmed SQL input when ActionOutput omits action_input."""
    if not isinstance(llm_reply, str) or not llm_reply.strip():
        return None
    try:
        steps = ReActOutputParser().parse(llm_reply)
    except Exception:
        logger.debug("Unable to parse sub-agent ReAct reply for SQL recovery.")
        return None
    for step in reversed(steps):
        if (step.action or "").lower() == "sql_query":
            return _extract_sql_action_input(step.action_input)
    return None


# Tool names a sub-agent is allowed to use. Taken from the factory's 8 tools
# plus the module-level skill tools. Intentionally EXCLUDES
# ``dispatch_parallel_tasks`` (anti-recursion fan-out) and ``todowrite``
# (sub-agents do not maintain a task list; it lives in the main loop).
_SUBAGENT_FACTORY_TOOL_NAMES = [
    "load_skill",
    "load_tools",
    "knowledge_retrieve",
    "sql_query",
    "code_interpreter",
    "shell_interpreter",
    "execute_skill_script_file",
    "html_interpreter",
]


_SUB_AGENT_PROMPT_TEMPLATE = """\
You are a DB-GPT sub-agent executing ONE focused sub-task delegated by a lead
agent. You run in an isolated context — you CANNOT see the main conversation
history. Everything you need is in the goal (and optional context) below.

## Your sub-task goal
{goal}
{extra_context}

## ACTION SPACE (your available tools)
You operate resources ONLY through the tools listed below. You MUST use the
EXACT tool name shown here — do not invent names like ``run_sql`` / ``run_python``.
All tools are read-only; you CANNOT perform write operations. If your task
needs a write, return a recommendation for the lead agent to act instead.
Use the database / knowledge base / MCP connector named in your goal.

{{{{ action_space }}}}

## Rules
- You CANNOT delegate further (no parallel sub-tasks of your own).
- Keep your context tight; produce a concise, self-contained conclusion.
- When done, call ``terminate`` with your final result.

## Output formatting (IMPORTANT — keep results readable)
- One query/result per step. Prefer separate ``sql_query`` calls over packing
  many results into one ``code_interpreter`` print — each ``sql_query`` already
  returns a clean, properly newline-separated markdown table on its own.
- NEVER concatenate multiple tables into one blob. If you DO print markdown
  from ``code_interpreter``, every table row MUST be on its OWN line (``\\n``),
  and there MUST be a blank line between a table and any following heading or
  the next table. Do NOT glue ``| ... |### heading`` or ``| --- || row``.
- In ``code_interpreter``, use ``print(df.to_markdown(index=False))`` per table
  and ``print()`` (blank line) between tables — do not hand-build one big string.

## RESPONSE FORMAT (ReAct)
Every response MUST contain exactly one Action and one Action Input.
The Action MUST be one of [{{{{ action_space_names }}}}].
- Thought: analyze status and decide the next step
- Action Intention: what this step will do (short, user-facing)
- Action: the selected tool name (exactly as listed above)
- Action Input: the JSON tool parameters (empty if none required)

When the task is complete, use exactly:
Thought: ...
Action: terminate
Action Input: {{"result": "final answer"}}
"""


def _filter_readonly_connector_tools(
    connector_tool_extras: Optional[List[Any]],
    connector_manager: Any = None,
) -> List[Any]:
    """Filter connector (MCP) tools down to read-only ones for sub-agents.

    Write operations are identified exactly as ``ConfirmationRegistry`` does
    (confirmation.py): a tool whose name appears in any catalog entry's
    ``confirm_actions`` list requires confirmation, i.e. it is a write. Such
    tools are removed so a parallel sub-agent can never trigger concurrent
    write-confirmation popups (spec §4.5.1 point 4 / §6.4).

    Args:
        connector_tool_extras: Flat list of ``BaseTool`` from
            ``_select_connector_tools`` (or None).
        connector_manager: A ``ConnectorManager`` (exposes ``get_catalog()``).
            When None, the catalog cannot be consulted; to stay safe we drop
            ALL connector tools rather than risk injecting a write tool.

    Returns:
        The subset of tools that are safe (read-only) for a sub-agent.
    """
    if not connector_tool_extras:
        return []
    if connector_manager is None:
        # No catalog to classify with — fail safe: inject none.
        logger.warning(
            "sub-agent: connector_manager is None; dropping all %d connector "
            "tools to avoid injecting a write tool",
            len(connector_tool_extras),
        )
        return []

    try:
        catalog = connector_manager.get_catalog()
        write_tool_names: set = set()
        for entry in catalog.list():
            write_tool_names.update(entry.confirm_actions or [])
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(
            "sub-agent: failed to read connector catalog (%s); dropping all "
            "connector tools",
            e,
        )
        return []

    readonly = []
    dropped = []
    for t in connector_tool_extras:
        name = getattr(getattr(t, "_tool", None), "name", None) or getattr(
            t, "name", None
        )
        if name in write_tool_names:
            dropped.append(name)
        else:
            readonly.append(t)
    if dropped:
        logger.info(
            "sub-agent: filtered out %d write connector tool(s): %s",
            len(dropped),
            dropped,
        )
    return readonly


def _build_sub_prompt(goal: str, extra_context: Optional[str]) -> PromptTemplate:
    """Build the sub-agent system prompt from goal + optional context."""
    ctx_block = ""
    if extra_context and extra_context.strip():
        ctx_block = f"\n## Shared context from the lead agent\n{extra_context}\n"
    text = _SUB_AGENT_PROMPT_TEMPLATE.format(goal=goal, extra_context=ctx_block)
    return PromptTemplate(template=text, input_variables=[], template_format="jinja2")


async def build_sub_react_agent(
    sub_goal: str,
    sub_index: int,
    *,
    parent_conv_id: str,
    llm_client: Any,
    sub_model_name: Optional[str] = None,
    database_connector: Any = None,
    knowledge_resources: Any = None,
    readonly_connector_tools: Optional[List[Any]] = None,
    extra_context: Optional[str] = None,
    batch_id: int = 0,
):
    """Construct an isolated child ReActAgent for one sub-task.

    Args:
        sub_goal: Self-contained objective for this sub-agent.
        sub_index: Index within the dispatch batch (drives conv_id / lane).
        parent_conv_id: The lead agent's conv_id.
        llm_client: The lead agent's ``LLMClient`` (reused, not the config).
        sub_model_name: Model for the sub-agent; None => same as main model.
        database_connector: Shared read-only DB connector (or None).
        knowledge_resources: Shared read-only knowledge resources (or None).
        readonly_connector_tools: Pre-filtered read-only MCP tools (or None).
        extra_context: Optional shared background spliced into the prompt.
        batch_id: Dispatch-batch sequence number. Folded into ``sub_conv_id``
            so repeated dispatch calls in the same conversation do NOT reuse
            the same working directory / agent_id (which would overwrite the
            previous batch's sub-agent row and cross-contaminate artifacts).

    Returns:
        ``(sub_agent, sub_conv_id, sub_state)``.
    """
    from dbgpt.agent import AgentContext, AgentMemory
    from dbgpt.agent.core.memory.gpts import DefaultGptsPlansMemory, GptsMemory
    from dbgpt.agent.expand.react_agent import ReActAgent
    from dbgpt_serve.agent.agents.db_gpts_memory import MetaDbGptsMessageMemory

    # (1) Independent conv_id — the workspace-isolation anchor. Drives the
    # subprocess cwd pilot/tmp/{conv_id} inside code_interpreter / shell.
    # The ``d{batch_id}`` segment makes each dispatch batch's sub-agents get
    # their OWN directory, so batch 2's sub_0 cannot read/overwrite batch 1's
    # sub_0 artifacts (a real cross-batch data-leak before this).
    sub_conv_id = f"{parent_conv_id}__d{batch_id}_sub_{sub_index}"

    # (2) Independent react_state — artifact bookkeeping isolation. A fresh
    # dict means generated_images / image_url_map etc. never cross-write.
    sub_state = {"conv_id": sub_conv_id, "file_path": None}

    # (3) Independent AgentMemory — not cached in REACT_AGENT_MEMORY_CACHE,
    # so the sub-agent's history never pollutes the parent's memory.
    sub_gpt_memory = GptsMemory(
        plans_memory=DefaultGptsPlansMemory(),
        message_memory=MetaDbGptsMessageMemory(),
    )
    sub_gpt_memory.init(sub_conv_id, enable_vis_message=False)
    sub_agent_memory = AgentMemory(gpts_memory=sub_gpt_memory)

    # (4) Independent tool set — factory rebuilds the 8 tools capturing
    # sub_state. Shared read-only DB / knowledge resources are passed through.
    # MCP/connector tools are shared objects (stateless per-call sessions),
    # already filtered to read-only by the caller.
    sub_tools = make_react_tools(
        sub_state,
        database_connector=database_connector,
        knowledge_resources=knowledge_resources,
    )
    sub_tool_pack = ToolPack(
        [sub_tools[name] for name in _SUBAGENT_FACTORY_TOOL_NAMES]
        + (readonly_connector_tools or [])
        + [Terminate()]
    )

    # (5) Rebuild LLMConfig reusing the client. None model => Default strategy
    # (picks the same model the worker manager serves = parent's default).
    if sub_model_name:
        sub_llm_config = LLMConfig(
            llm_client=llm_client,
            llm_strategy=LLMStrategyType.Priority,
            strategy_context=json.dumps([sub_model_name]),
        )
    else:
        sub_llm_config = LLMConfig(llm_client=llm_client)

    sub_context = AgentContext(
        conv_id=sub_conv_id,
        gpts_app_code="react_agent_sub",
        gpts_app_name="ReAct-Sub",
        language="zh",
        enable_context_management=True,
    )

    sub_agent = await (
        ReActAgent(max_retry_count=_SUBAGENT_MAX_RETRY)
        .bind(sub_context)
        .bind(sub_agent_memory)
        .bind(sub_llm_config)
        .bind(sub_tool_pack)
        .bind(_build_sub_prompt(sub_goal, extra_context))
        .build()
    )
    return sub_agent, sub_conv_id, sub_state


# Lead-agent delegation rubric. Kept here as a module constant so the long
# prompt text does NOT bloat agentic_data_api.py; the main link imports and
# splices it into the full-tool system prompt (plan stage 4 / spec §4.6).
DISPATCH_PROMPT_SECTION = """\
## Task Decomposition and Parallel Execution (todowrite + dispatch_parallel_tasks)

[Run a parallel-eligibility check at the start of every round]
Before selecting the first tool, evaluate the user's task by meaning and
structure. Parallel dispatch is required when all of the following are true:
1. The task can be split into at least 2 clearly scoped subtasks, each capable
   of producing a useful result on its own.
2. The subtasks have no ordering dependency; none must wait for another result.
3. Each subtask needs its own query, research, analysis, or content production
   and is substantial enough to benefit from an isolated context.
4. Each subtask can be expressed as a self-contained goal with the required
   database, table, knowledge base, or connector information.

When all conditions are satisfied, you MUST execute
`todowrite -> dispatch_parallel_tasks`, even if the overall task has fewer than
3 steps. Do not avoid parallel execution merely because there are only 2
independent subtasks.

Natural-language structures such as "separately", "respectively",
"simultaneously", "in parallel", or requests covering multiple objects
(regions, topics, data sources, or reports) are strong candidate signals.
Do not rely on keyword matching alone; always apply the independence criteria
above. Proactively use parallel execution when the task qualifies, even if the
user does not explicitly ask for sub-agents.

This is a mandatory two-stage workflow and the order must be preserved:

[Stage 1: Decompose] Use `todowrite` to turn the task into a structured todo
list. `todowrite` is the only entry point for decomposition; every multi-step
task must be decomposed there first.

[Stage 2: Execute] After decomposition, use `dispatch_parallel_tasks` to assign
multiple independent todo items with no ordering dependency to sub-agents in
parallel. Each sub-agent executes exactly one decomposed item. Sub-agents are
an execution mechanism after decomposition, not a decomposition tool.

[Mandatory rules]
- Never skip `todowrite` and call `dispatch_parallel_tasks` directly. A todo
  list must exist first, and every dispatched subtask must correspond to an
  item in that list.
- Keep exactly one todo item marked as `in_progress`. This is a progress-board
  constraint only; other eligible independent `pending` items may still be
  included in the same dispatch batch.
- As soon as all parallel subtasks return, call `todowrite` again and mark
  those items as `completed`. The dispatch tool does not update todo state.
- Do not parallelize dependent tasks. Complete the prerequisite first, then
  pass its result through `context` to the dependent item in a later round.

[Good candidates for parallel dispatch]
- Research multiple independent data sources or MCP connectors that do not
  share intermediate results.
- Produce separate analyses for multiple independent objects, such as three
  reports or three unrelated topics.
- Run multiple independent read-only queries or analyses against the same
  database or table. For example, analyze the `users` table's country
  distribution and registration-year distribution separately when neither
  analysis needs the other's intermediate result.
- Execute any set of todo items that have no data dependency and can all start
  immediately.

[Do not use parallel dispatch]
- Steps share intermediate results, cleaning state, or must reuse the same
  computed metric definition.
- Todo items are dependent, such as cleaning before forecasting or when B
  requires A's result.
- The task is a simple, single-step operation; execute it directly without
  creating a todo list.

[Usage rules]
- Every subtask goal must be self-contained. A sub-agent cannot see the current
  conversation history, so put all required information in `goal` or `context`.
- Sub-agents inherit database, knowledge-base, and read-only MCP tools, but do
  not know which resource to use by default. Name the required database and
  relevant tables, knowledge base, or MCP connector in every goal/context.
  Sub-agents are read-only; the lead agent must perform write operations.
- Dispatch at most N subtasks per call. Excess tasks are truncated and reported;
  dispatch additional batches when necessary.
- A sub-agent must never call `dispatch_parallel_tasks` recursively.
"""


def make_dispatch_tool(
    *,
    parent_conv_id: str,
    llm_client: Any,
    sub_model_name: Optional[str] = None,
    database_connector: Any = None,
    knowledge_resources: Any = None,
    connector_tool_extras: Optional[List[Any]] = None,
    connector_manager: Any = None,
    emit_event: Any,
    max_parallel: int = 3,
):
    """Build the ``dispatch_parallel_tasks`` tool bound to the lead context.

    Args:
        parent_conv_id: The lead agent's conv_id (sub conv_ids derive from it).
        llm_client: The lead agent's ``LLMClient`` (reused for sub-agents).
        sub_model_name: Sub-agent model; None => same as main model.
        database_connector: Shared read-only DB connector (or None).
        knowledge_resources: Shared read-only knowledge resources (or None).
        connector_tool_extras: The lead agent's MCP tools (filtered read-only
            here before being shared with sub-agents).
        connector_manager: ``ConnectorManager`` for the read-only filter.
        emit_event: ``async (payload: dict) -> None`` — injected callback that
            puts SSE events on the stream queue. Keeps the dispatcher
            decoupled from the queue itself (testable).
        max_parallel: Hard cap on concurrent sub-agents per call.

    Returns:
        The ``dispatch_parallel_tasks`` tool (a ``@tool``-wrapped callable).
    """
    # Filter the lead agent's MCP tools to read-only ONCE, then share with
    # every sub-agent (the tool objects are stateless per-call — safe to share).
    readonly_connector_tools = _filter_readonly_connector_tools(
        connector_tool_extras, connector_manager
    )

    # Per-lead-agent dispatch counter. Each ``dispatch_parallel_tasks`` call
    # bumps it and folds the value into every sub-agent's ``agent_id`` /
    # ``sub_conv_id``. Without this, batch 2's ``sub_0`` would reuse batch 1's
    # ``sub_0`` working directory (cross-batch artifact leak) and the frontend
    # ``subAgents[agent_id]`` map would overwrite the earlier row.
    _dispatch_counter = 0

    @tool(
        description=(
            "把多个【相互独立、无依赖】的子任务并行交给子 Agent 执行，返回各自"
            "结果。任务包含至少 2 个可独立交付、可同时开始、且各自值得独立上下文"
            "的目标时使用。同一数据库或同一张表上的独立只读分析也可以并行；只有"
            "共享中间结果、计算状态或存在前后依赖时才应串行。"
            f"单次最多 {max_parallel} 个子任务，超出请分批多轮调用。"
            '参数: {"tasks": [{"goal": "...", "context": "...", "title": "..."}]}'
        )
    )
    async def dispatch_parallel_tasks(tasks: list) -> str:
        nonlocal _dispatch_counter
        if not isinstance(tasks, list) or not tasks:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Error: tasks 必须是非空列表",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Cap to the concurrency limit; report what was dropped (no silent cap).
        accepted = tasks[:max_parallel]
        dropped = len(tasks) - len(accepted)

        # Stable, unique batch id for this dispatch call. Folded into every
        # sub-agent's id / conv_id so repeated dispatches never collide.
        _dispatch_counter += 1
        batch_id = _dispatch_counter

        async def run_one(idx: int, t: dict) -> dict:
            started_at = time.monotonic()
            agent_id = f"sub_d{batch_id}_{idx}"
            title = (
                t.get("title") if isinstance(t, dict) else None
            ) or f"子任务{idx + 1}"
            goal = (t.get("goal") if isinstance(t, dict) else None) or ""
            extra = t.get("context") if isinstance(t, dict) else None
            await emit_event(
                {
                    "type": "agent.start",
                    "agent_id": agent_id,
                    "agent_name": title,
                    "goal": goal,
                    "lane": idx,
                    "batch_id": batch_id,
                }
            )
            try:
                agent, _cid, sub_state = await build_sub_react_agent(
                    goal,
                    idx,
                    parent_conv_id=parent_conv_id,
                    llm_client=llm_client,
                    sub_model_name=sub_model_name,
                    database_connector=database_connector,
                    knowledge_resources=knowledge_resources,
                    readonly_connector_tools=readonly_connector_tools,
                    extra_context=extra,
                    batch_id=batch_id,
                )
                from dbgpt.agent import AgentMessage

                # Forward the sub-agent's CONFIRMED tool actions (not raw token
                # thinking) as agent.step events tagged with this agent_id, so
                # the frontend can show a live "current action" line and a
                # drill-down step list. These go through emit_event on their own
                # channel — they never enter the main loop's round_step_map
                # (which keys steps by round_num and would collide across
                # parallel sub-agents).
                pending_sql_by_round: Dict[int, str] = {}

                async def _sub_stream_callback(
                    event_type: str, payload: dict, _aid: str = agent_id
                ) -> None:
                    round_num = int(payload.get("round") or 0)
                    if event_type == "thinking":
                        sql = _extract_sql_from_llm_reply(payload.get("llm_reply"))
                        if sql:
                            pending_sql_by_round[round_num] = sql
                        return
                    if event_type != "act":
                        return
                    ao = payload.get("action_output") or {}
                    if ao.get("terminate"):
                        return
                    action = ao.get("action")
                    if not action or action.lower() == "terminate":
                        return
                    # Parse the raw observation into STRUCTURED display chunks
                    # for the right-panel process view (Devin-style). The tool
                    # result is a {"chunks":[...]} wrapper (or several concat'd);
                    # we unwrap so the frontend renders markdown tables / code /
                    # json / images properly instead of showing the raw JSON
                    # string. Images are kept inline (same as the main agent's
                    # OutputRenderer) AND also flow via subagent.artifacts for
                    # the files tab / preview / download.
                    raw_obs = ao.get("observations") or ao.get("content") or ""
                    chunks = _parse_observation_chunks(raw_obs)
                    # Per-chunk truncation keeps SSE light without cutting a
                    # table in half mid-cell. HTML report chunks are EXEMPT from
                    # the small text cap — truncating an HTML document yields an
                    # unclosed, broken ``srcDoc`` that the iframe cannot render
                    # ("report cut off"). They get a much larger guard instead.
                    # Image chunks are tiny (just a /images/... URL), so no cap.
                    for c in chunks:
                        content = c.get("content")
                        if not isinstance(content, str):
                            continue
                        if c.get("output_type") == "html":
                            limit = _SUBAGENT_HTML_MAX_CHARS
                        elif c.get("output_type") == "image":
                            continue
                        else:
                            limit = _SUBAGENT_OBS_MAX_CHARS
                        if len(content) > limit:
                            c["content"] = content[:limit] + "…（已截断）"
                    step_event = {
                        "type": "agent.step",
                        "agent_id": _aid,
                        "batch_id": batch_id,
                        "action": action,
                        "intention": ao.get("action_intention"),
                        "chunks": chunks,
                        "round": payload.get("round"),
                    }
                    if action.lower() == "sql_query":
                        sql = _extract_sql_action_input(
                            ao.get("action_input")
                        ) or pending_sql_by_round.pop(round_num, None)
                        if sql:
                            step_event["sql"] = sql
                    await emit_event(step_event)

                reply = await asyncio.wait_for(
                    agent.generate_reply(
                        received_message=AgentMessage(content=goal),
                        sender=agent,
                        stream_callback=_sub_stream_callback,
                    ),
                    timeout=_SUBAGENT_TIMEOUT,
                )
                r = extract_subagent_result(reply, sub_state, title, "done")
            except asyncio.TimeoutError:
                r = {
                    "title": title,
                    "status": "timeout",
                    "result": f"子任务超时（{_SUBAGENT_TIMEOUT}s）",
                    "artifacts": [],
                }
            except Exception as e:  # single failure must not break the batch
                logger.warning("sub-agent %d failed: %s", idx, e, exc_info=True)
                r = {
                    "title": title,
                    "status": "failed",
                    "result": f"执行失败: {e}",
                    "artifacts": [],
                }
            # Stamp the source agent on every artifact so the frontend can
            # count/label per sub-agent (aggregate-card row + files-tab tag).
            attach_agent_attribution(r.get("artifacts", []), agent_id, title)
            r["agent_id"] = agent_id
            r["agent_name"] = title
            result_summary = str(r.get("result") or "")
            if len(result_summary) > _SUBAGENT_RESULT_SUMMARY_MAX_CHARS:
                result_summary = (
                    result_summary[:_SUBAGENT_RESULT_SUMMARY_MAX_CHARS]
                    + "\n\n…（完整结果请查看子任务详情）"
                )
            await emit_event(
                {
                    "type": "agent.done",
                    "agent_id": agent_id,
                    "batch_id": batch_id,
                    "status": r["status"],
                    "result": result_summary,
                    "elapsed_ms": int((time.monotonic() - started_at) * 1000),
                }
            )
            return r

        results = await asyncio.gather(*[run_one(i, t) for i, t in enumerate(accepted)])

        # Artifacts go to the frontend out-of-band — NOT into the lead context.
        # Each item already carries its source agent_id / agent_name (stamped
        # above), so the frontend can do per-row counting and "by <agent>" labels.
        all_artifacts = [a for r in results for a in r.get("artifacts", [])]
        if all_artifacts:
            await emit_event({"type": "subagent.artifacts", "items": all_artifacts})

        # Only the compressed text conclusions are relayed to the lead LLM.
        summary = "\n\n".join(
            f"### {r['title']} [{r['status']}]\n{r['result']}" for r in results
        )
        if dropped > 0:
            summary += (
                f"\n\n⚠️ 另有 {dropped} 个子任务因超过并发上限未执行，"
                f"请在下一轮再次调用 dispatch_parallel_tasks 处理。"
            )
        return json.dumps(
            {"chunks": [{"output_type": "markdown", "content": summary}]},
            ensure_ascii=False,
        )

    return dispatch_parallel_tasks
