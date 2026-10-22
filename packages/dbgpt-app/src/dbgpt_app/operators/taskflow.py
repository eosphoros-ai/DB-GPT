"""TaskFlow product-level operators.

Coarse-grained, data-analysis oriented operators used by the TaskFlow DSL
compiler (`dbgpt_serve.flow.taskflow`). Unlike the low-level AWEL operators,
each operator here maps to one *product* node in the TaskFlow editor:

- ``TFStepMarkerOperator``: generic wrapper that prepends a ``vis-flow-step``
  marker block to any string payload, so the chat UI can render a truthful,
  ordered step trace from the final stream text.
- ``HOFileDataOperator``: load an uploaded CSV/Excel file as an analysis
  dataset (markdown table + shared DataFrame).
- ``HODataAnalysisOperator``: LLM-driven analysis over upstream data, produces
  conclusions (clean data channel on out0).
- ``HOChartAdvisorOperator``: LLM proposes charts (SQL-based when a datasource
  is bound, column-based over a shared DataFrame otherwise) and renders a
  dashboard via gpt-vis.
- ``HOHumanConfirmOperator``: P0 soft confirmation node (ordering + step
  marker only; real pause/resume lands in P1).

Marker protocol: operators that produce *content* keep their out0 clean for
downstream LLM consumers; the compiler inserts ``TFStepMarkerOperator`` on the
branch that feeds the final join, so markers appear exactly once in the final
answer text, in execution order.
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from dbgpt._private.config import Config
from dbgpt.agent.resource.database import DBResource
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    LLMClient,
    ModelMessage,
)
from dbgpt.core.awel import BaseOperator, JoinOperator, MapOperator
from dbgpt.core.awel.dag.base import DAGContext
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    Parameter,
    ViewMetadata,
    ui,
)
from dbgpt.core.awel.task.base import TaskOutput
from dbgpt.core.awel.task.task_impl import SimpleTaskOutput
from dbgpt.core.awel.trigger.http_trigger import CommonLLMHttpRequestBody
from dbgpt.core.interface.llm import ModelRequest
from dbgpt.model.operators import MixinLLMOperator
from dbgpt.util.i18n_utils import _
from dbgpt.util.pd_utils import df_to_markdown
from dbgpt.vis.tags.vis_chart import default_chart_type_prompt

from .datasource import GPTVisMixin

logger = logging.getLogger(__name__)

CFG = Config()

TASKFLOW_STEP_VIS_TAG = "vis-flow-step"

#: Share-data key where HOFileDataOperator stores the loaded DataFrame.
SHARE_KEY_TASKFLOW_FILE_DF = "__taskflow_file_dataframe__"


_BACKTICK_RUN_RE = re.compile(r"`{3,}")


def _sanitize_marker_text(text: Any) -> Any:
    """Neutralize ``` runs inside marker payloads.

    The frontend splits marker blocks on the first ``` sequence; LLM-authored
    details (thoughts, tool inputs) routinely contain backtick runs which
    would truncate the JSON and leak raw fragments into the answer text.
    """
    if isinstance(text, str):
        return _BACKTICK_RUN_RE.sub("``", text)
    return text


def build_step_marker(
    step_id: str,
    label: str,
    kind: str,
    status: str = "success",
    duration_ms: int = 0,
    summary: Optional[str] = None,
    steps: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build a ``vis-flow-step`` marker block for the chat step card.

    ``steps`` carries a structured, recent slice of an agent node's ReAct
    trace (``[{kind, title, detail}]``) so the chat UI can render compact
    tool-call rows; it is transient (live events) and never persisted into
    the final stored answer.
    """
    payload = {
        "step_id": step_id,
        "label": _sanitize_marker_text(label),
        "kind": kind,
        "status": status,
        "duration_ms": duration_ms,
    }
    if summary:
        payload["summary"] = _sanitize_marker_text(summary)
    if steps:
        payload["steps"] = [
            {
                **s,
                "title": _sanitize_marker_text(s.get("title", "")),
                "detail": _sanitize_marker_text(s.get("detail", "")),
            }
            for s in steps
        ]
    return (
        f"```{TASKFLOW_STEP_VIS_TAG}\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        "```\n\n"
    )


def strip_step_markers(text: str) -> str:
    """Remove all ``vis-flow-step`` marker blocks from text.

    Used when upstream text may carry markers and is about to be fed into an
    LLM prompt (markers are a UI protocol, not content).
    """
    if not text or TASKFLOW_STEP_VIS_TAG not in text:
        return text or ""
    out, rest = [], text
    while TASKFLOW_STEP_VIS_TAG in rest:
        before, _, after = rest.partition(f"```{TASKFLOW_STEP_VIS_TAG}")
        out.append(before)
        _, sep, rest = after.partition("```")
        if not sep:
            break
    out.append(rest)
    return "".join(out).strip()


#: Fence tag carrying a node's first-class artifacts (metadata only — the
#: payloads live on disk and are served via the scoped artifact-file
#: endpoint). Design: docs/design/flow-output-artifacts-mockup.html §2.
TASKFLOW_ARTIFACT_VIS_TAG = "vis-flow-artifact"

_ARTIFACT_FENCE_RE = re.compile(r"```vis-flow-artifact\s*\n[\s\S]*?```")


def strip_artifact_fences(text: str) -> str:
    """Remove ``vis-flow-artifact`` fences (artifact metadata is UI
    protocol, not LLM material)."""
    if not text or TASKFLOW_ARTIFACT_VIS_TAG not in text:
        return text or ""
    return _ARTIFACT_FENCE_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Step marker operator
# ---------------------------------------------------------------------------

_PARAMETER_STEP_ID = Parameter.build_from(
    _("Step ID"),
    "step_id",
    str,
    optional=True,
    default=None,
    description=_("The TaskFlow DSL node id this marker belongs to."),
)
_PARAMETER_STEP_LABEL = Parameter.build_from(
    _("Step Label"),
    "step_label",
    str,
    optional=True,
    default=None,
    description=_("The product label of the TaskFlow DSL node."),
)
_PARAMETER_STEP_KIND = Parameter.build_from(
    _("Step Kind"),
    "step_kind",
    str,
    optional=True,
    default=None,
    description=_("The TaskFlow DSL node kind."),
)
_PARAMETER_STEP_SUMMARY = Parameter.build_from(
    _("Step Summary"),
    "step_summary",
    str,
    optional=True,
    default=None,
    description=_("A short static summary shown on the step card."),
)

_STEP_PARAMETERS = [
    _PARAMETER_STEP_ID,
    _PARAMETER_STEP_LABEL,
    _PARAMETER_STEP_KIND,
    _PARAMETER_STEP_SUMMARY,
]

#: Share-data keys for step timing (written by TFStepClockOperator / markers).
_SHARE_KEY_DAG_START_TS = "__taskflow_dag_start_ts__"
_SHARE_KEY_LAST_STEP_TS = "__taskflow_last_step_ts__"
#: Share-data key where HODatasourceExecutorOperator stores the result df.
_SHARE_KEY_EXECUTOR_DF = "__datasource_executor_result__"
#: Share-data key where TFStepClockOperator stores the chat conversation uid
#: (used by step markers to push live step events to the SSE channel).
SHARE_KEY_TASKFLOW_CONV_UID = "__taskflow_conv_uid__"

# ---------------------------------------------------------------------------
# Live step events: markers push each completed step payload to a per-chat
# queue; the flow service merges the queue into the SSE stream so the chat UI
# renders a node result as soon as its node finishes, instead of waiting for
# the final join at the end of the DAG.
# ---------------------------------------------------------------------------
_STEP_EVENT_QUEUES: Dict[str, "asyncio.Queue[str]"] = {}


def register_step_events(conv_uid: str) -> "asyncio.Queue[str]":
    """Create and register the live step-event queue for a chat."""
    queue: "asyncio.Queue[str]" = asyncio.Queue()
    _STEP_EVENT_QUEUES[conv_uid] = queue
    return queue


def unregister_step_events(conv_uid: str) -> None:
    """Remove the live step-event queue of a chat (run finished)."""
    _STEP_EVENT_QUEUES.pop(conv_uid, None)


def get_step_event_queue(conv_uid: Optional[str]) -> "Optional[asyncio.Queue[str]]":
    """Return the live step-event queue registered for a chat, if any."""
    if not conv_uid:
        return None
    return _STEP_EVENT_QUEUES.get(conv_uid)


class TFLastOutputOperator(JoinOperator[str]):
    """Join that outputs only the LAST input (the previous node's result).

    Structurally it keeps every step marker wired into a single leaf (the
    chat_flow channel requires exactly one leaf), but the emitted value is
    just the immediately-previous node's marker + content instead of the
    whole concatenated bundle.
    """

    metadata = ViewMetadata(
        label=_("TaskFlow Last Output Operator"),
        name="taskflow_last_output_operator",
        description=_("Output only the last input (previous node's result)."),
        category=OperatorCategory.COMMON,
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Inputs"),
                "inputs",
                str,
                is_list=True,
                description=_("The step marker payloads of all nodes."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Final answer"),
                "answer",
                str,
                description=_("The previous node's marker + content."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, **kwargs):
        super().__init__(combine_function=self._last, **kwargs)

    @staticmethod
    def _last(*args: str) -> str:
        for value in reversed(args):
            if isinstance(value, str) and value:
                return value
        return ""


class TFStepClockOperator(BaseOperator[str]):
    """Record the flow start timestamp and the chat conversation uid.

    Inserted right after the trigger by the TaskFlow compiler so step markers
    can compute real per-node durations against a shared start time, and so
    they can push live step events to the SSE channel of the current chat.
    """

    metadata = ViewMetadata(
        label=_("TaskFlow Step Clock"),
        name="taskflow_step_clock_operator",
        description=_("Record the TaskFlow start timestamp (pass-through)."),
        category=OperatorCategory.COMMON,
        parameters=[],
        inputs=[
            IOField.build_from(
                _("User message"),
                "user_message",
                str,
                description=_("The user message from the trigger."),
            ),
            IOField.build_from(
                _("Request body"),
                "request_body",
                CommonLLMHttpRequestBody,
                description=_(
                    "The full request body from the trigger (carries conv_uid "
                    "for live step events)."
                ),
            ),
        ],
        outputs=[
            IOField.build_from(
                _("User message"),
                "user_message",
                str,
                description=_("The unchanged user message."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[str]:
        """Record the start ts / conv_uid and pass the message through."""
        curr_task_ctx = dag_ctx.current_task_context
        message = ""
        conv_uid: Optional[str] = None
        for parent in curr_task_ctx.task_input.parent_outputs:
            task_output = parent.task_output
            if not task_output or task_output.is_empty or task_output.is_stream:
                continue
            value = task_output.output
            if isinstance(value, str):
                message = value
            elif isinstance(value, dict):
                conv_uid = value.get("conv_uid") or conv_uid
            else:
                conv_uid = getattr(value, "conv_uid", None) or conv_uid
        await dag_ctx.save_to_share_data(
            _SHARE_KEY_DAG_START_TS, time.monotonic(), overwrite=True
        )
        if conv_uid:
            await dag_ctx.save_to_share_data(
                SHARE_KEY_TASKFLOW_CONV_UID, conv_uid, overwrite=True
            )
        output: TaskOutput[str] = SimpleTaskOutput(message)
        curr_task_ctx.set_task_output(output)
        return output


class TFStepMarkerOperator(MapOperator[str, str]):
    """Prepend a ``vis-flow-step`` marker to the upstream string payload.

    Durations use a monotonic timestamp chain: each marker measures the
    elapsed time since the previous marker (or the flow clock for the first
    one), which approximates the product node's execution time in the
    sequential AWEL runner.
    """

    metadata = ViewMetadata(
        label=_("TaskFlow Step Marker"),
        name="taskflow_step_marker_operator",
        description=_("Prepend a TaskFlow step marker to the upstream payload."),
        category=OperatorCategory.COMMON,
        parameters=[p.new() for p in _STEP_PARAMETERS],
        inputs=[
            IOField.build_from(
                _("Content"), "content", str, description=_("The upstream content.")
            )
        ],
        outputs=[
            IOField.build_from(
                _("Marked content"),
                "marked_content",
                str,
                description=_("The content prefixed with a step marker."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        step_id: Optional[str] = None,
        step_label: Optional[str] = None,
        step_kind: Optional[str] = None,
        step_summary: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._step_id = step_id
        self._step_label = step_label
        self._step_kind = step_kind
        self._step_summary = step_summary

    async def _measure_duration_ms(self) -> int:
        try:
            now = time.monotonic()
            dag_ctx = self.current_dag_context
            last = await dag_ctx.get_from_share_data(_SHARE_KEY_LAST_STEP_TS)
            if last is None:
                last = await dag_ctx.get_from_share_data(_SHARE_KEY_DAG_START_TS)
            await dag_ctx.save_to_share_data(
                _SHARE_KEY_LAST_STEP_TS, now, overwrite=True
            )
            if last is None:
                return 0
            return max(0, int((now - last) * 1000))
        except Exception:
            # Standalone use (no DAG context): no timing available.
            return 0

    async def _row_count_summary(self) -> Optional[str]:
        """Attach the result row count for db_query steps (if available)."""
        if self._step_kind != "db_query":
            return self._step_summary
        try:
            df = await self.current_dag_context.get_from_share_data(
                _SHARE_KEY_EXECUTOR_DF
            )
            if df is None:
                return self._step_summary
            count = f"{len(df):,}"
            language = (
                self.system_app.config.get_current_lang() if self.system_app else "zh"
            )
            return f"{count} 行" if language == "zh" else f"{count} rows"
        except Exception:
            return self._step_summary

    async def map(self, content: str) -> str:
        """Attach the marker to the content."""
        if not self._step_id:
            return content or ""
        duration_ms = await self._measure_duration_ms()
        summary = await self._row_count_summary()
        marker = build_step_marker(
            step_id=self._step_id,
            label=self._step_label or self._step_id,
            kind=self._step_kind or "unknown",
            duration_ms=duration_ms,
            summary=summary,
        )
        payload = marker + (content or "")
        await self._push_step_event(payload)
        return payload

    async def _push_step_event(self, payload: str) -> None:
        """Push the completed step payload to the live SSE channel (if any).

        The final join at the end of the DAG still carries every marker, so
        this side channel is purely additive: the chat UI deduplicates
        sections by step_id and the stored history stays unchanged.
        """
        try:
            conv_uid = await self.current_dag_context.get_from_share_data(
                SHARE_KEY_TASKFLOW_CONV_UID
            )
            queue = get_step_event_queue(conv_uid)
            if queue is not None:
                queue.put_nowait(payload)
        except Exception:
            # Live progress is best-effort; never break the DAG for it.
            pass


# ---------------------------------------------------------------------------
# File data operator
# ---------------------------------------------------------------------------


class HOFileDataOperator(MapOperator[str, str]):
    """Load a CSV/Excel file as the analysis dataset."""

    metadata = ViewMetadata(
        label=_("TaskFlow File Data Operator"),
        name="taskflow_file_data_operator",
        description=_("Load an uploaded CSV/Excel file as the analysis dataset."),
        category=OperatorCategory.DATABASE,
        parameters=[
            Parameter.build_from(
                _("File Name"),
                "file_name",
                str,
                optional=True,
                default=None,
                description=_("The file name or path of the uploaded CSV/Excel file."),
            ),
            Parameter.build_from(
                _("File ID"),
                "file_id",
                str,
                optional=True,
                default=None,
                description=_(
                    "The file id of the file uploaded via the file service "
                    "(bucket 'dbgpt'). Takes precedence over file_name."
                ),
            ),
            Parameter.build_from(
                _("Max Rows"),
                "max_rows",
                int,
                optional=True,
                default=1000,
                description=_("The maximum number of rows to load."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("User question"),
                "query",
                str,
                description=_("The user question (used for context only)."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Markdown table"),
                "markdown",
                str,
                description=_("The loaded dataset as a markdown table."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        file_name: Optional[str] = None,
        file_id: Optional[str] = None,
        max_rows: int = 1000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._file_name = file_name
        self._file_id = file_id
        self._max_rows = max_rows

    def _resolve_path(self) -> str:
        if self._file_id:
            return self._resolve_uploaded_path(self._file_id)
        candidates = [self._file_name]
        data_dir = getattr(CFG, "DATA_DIR", None)
        if data_dir:
            candidates.append(os.path.join(data_dir, self._file_name))
        for path in candidates:
            if path and os.path.exists(path):
                return path
        raise FileNotFoundError(f"TaskFlow file not found: {self._file_name}")

    def _resolve_uploaded_path(self, file_id: str) -> str:
        """Resolve an uploaded file (bucket 'dbgpt') to a local path.

        Fast path: the bytes are usually already on this node (the storage
        backend writes ``{bucket}/{file_id}[_{node_hash}]`` locally). That
        avoids the distributed HTTP fetch, which breaks when the uploader's
        node address went stale (e.g. the machine's IP changed between the
        upload and this run). The returned path keeps the original extension
        so the CSV/Excel dispatch in ``map`` keeps working.
        """
        import glob as _glob
        import shutil

        data_dir = getattr(CFG, "DATA_DIR", None) or os.path.join(
            os.path.expanduser("~"), ".cache", "dbgpt"
        )
        dest_dir = os.path.join(data_dir, "taskflow_files")
        os.makedirs(dest_dir, exist_ok=True)
        extension = os.path.splitext(self._file_name or "")[1] or ".csv"
        dest = os.path.join(dest_dir, file_id + extension)
        if os.path.exists(dest):
            return dest

        home_cache = os.path.join(os.path.expanduser("~"), ".cache", "dbgpt", "files")
        for pattern in (
            os.path.join(home_cache, "dbgpt", f"{file_id}*"),
            os.path.join(data_dir, "file_server_*", "dbgpt", f"{file_id}*"),
            os.path.join(data_dir, "dbgpt", f"{file_id}*"),
        ):
            hits = sorted(_glob.glob(pattern))
            if hits:
                shutil.copyfile(hits[0], dest)
                return dest

        from dbgpt.core.interface.file import FileStorageClient

        try:
            client = FileStorageClient.get_instance(CFG.SYSTEM_APP)
            file_data, metadata = client.get_file_by_id("dbgpt", file_id)
        except Exception as e:
            raise FileNotFoundError(
                f"TaskFlow uploaded file not found: {file_id} ({e})"
            ) from e
        extension = os.path.splitext(metadata.file_name)[1] or extension
        dest = os.path.join(dest_dir, file_id + extension)
        if not os.path.exists(dest):
            with open(dest, "wb") as f:
                f.write(file_data.read())
        return dest

    async def map(self, query: str) -> str:
        """Load the file and return a markdown preview."""
        path = await self.blocking_func_to_async(self._resolve_path)
        lower = path.lower()
        if lower.endswith((".xlsx", ".xls")):
            df = await self.blocking_func_to_async(pd.read_excel, path)
        else:
            df = await self.blocking_func_to_async(pd.read_csv, path)
        df = df.head(self._max_rows)
        await self.current_dag_context.save_to_share_data(
            SHARE_KEY_TASKFLOW_FILE_DF, df, overwrite=True
        )
        markdown = df_to_markdown(df)
        header = (
            f"file: {os.path.basename(path)}, rows: {len(df)}, "
            f"columns: {len(df.columns)}\n\n"
        )
        return header + markdown


# ---------------------------------------------------------------------------
# Data analysis operator
# ---------------------------------------------------------------------------

_DEFAULT_ANALYSIS_PROMPT_ZH = """你是一位资深数据分析师。请基于用户的问题和提供的数据\
进行深入分析。

要求：
1. 先给出 3-5 条核心结论（要点式，加粗关键数字）
2. 识别趋势、异常波动与结构占比
3. 对异常给出可能的原因推断
4. 最后给出 1-3 条可执行建议

{extra_requirement}

用户问题：
{user_input}

数据（markdown 表格）：
{data_report}

请用与用户提问相同的语言，以 markdown 格式输出分析结论。"""

_DEFAULT_ANALYSIS_PROMPT_EN = """You are a senior data analyst. Analyze the data \
provided based on the user's question.

Requirements:
1. Start with 3-5 key findings (bullet points, bold key numbers)
2. Identify trends, anomalies and structural proportions
3. Infer possible causes for anomalies
4. End with 1-3 actionable recommendations

{extra_requirement}

User question:
{user_input}

Data (markdown table):
{data_report}

Please answer in the same language as the user's question, in markdown format."""


class HODataAnalysisOperator(MixinLLMOperator, JoinOperator[str]):
    """LLM-driven analysis over upstream data, produces conclusions."""

    metadata = ViewMetadata(
        label=_("TaskFlow Data Analysis Operator"),
        name="taskflow_data_analysis_operator",
        description=_("Analyze upstream data around the analysis objective."),
        category=OperatorCategory.DATABASE,
        parameters=[
            Parameter.build_from(
                _("Model Name"),
                "model",
                str,
                optional=True,
                default=None,
                description=_("The model name."),
            ),
            Parameter.build_from(
                _("LLM Client"),
                "llm_client",
                LLMClient,
                optional=True,
                default=None,
                description=_("The LLM client, use the default client if empty."),
            ),
            Parameter.build_from(
                _("Extra Analysis Requirement"),
                "analysis_prompt",
                str,
                optional=True,
                default=None,
                description=_(
                    "Extra requirement appended to the analysis prompt, e.g. "
                    "'focus on trend and YoY/MoM'."
                ),
                ui=ui.DefaultUITextArea(),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("User question"),
                "question",
                str,
                description=_("The analysis objective from the user."),
            ),
            IOField.build_from(
                _("Analysis data"),
                "analysis_data",
                str,
                description=_("Upstream data (markdown tables, conclusions)."),
                dynamic=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Analysis conclusion"),
                "conclusion",
                str,
                description=_("The analysis conclusion in markdown."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        analysis_prompt: Optional[str] = None,
        **kwargs,
    ):
        JoinOperator.__init__(self, combine_function=self._join_func, **kwargs)
        MixinLLMOperator.__init__(self, llm_client=llm_client, **kwargs)
        self._model = model
        self._analysis_prompt = analysis_prompt

    async def _join_func(self, question: str, *args) -> str:
        data_parts = [strip_step_markers(a) for a in args if isinstance(a, str) and a]
        data_report = "\n\n".join(p for p in data_parts if p)
        language = (
            self.system_app.config.get_current_lang() if self.system_app else "zh"
        )
        template = (
            _DEFAULT_ANALYSIS_PROMPT_ZH
            if language == "zh"
            else _DEFAULT_ANALYSIS_PROMPT_EN
        )
        prompt = template.format(
            extra_requirement=self._analysis_prompt or "",
            user_input=question,
            data_report=data_report,
        )
        messages = ModelMessage.from_base_messages(
            ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template("{input}")]
            ).format_messages(input=prompt)
        )
        models = await self.llm_client.models()
        if not models:
            raise Exception("No models available.")
        model = self._model or models[0].model
        model_request = ModelRequest.build_request(model, messages=messages)
        model_output = await self.llm_client.generate(model_request)
        return model_output.gen_text_with_thinking()


# ---------------------------------------------------------------------------
# Chart advisor operator
# ---------------------------------------------------------------------------

_DEFAULT_CHART_PROMPT_ZH = """你是一位数据可视化专家。请根据用户问题、分析结论和数据，\
设计最多 {max_charts} 张图表来讲清楚数据结论。

可用图表类型：
{display_type}

{data_hint}

要求：
1. 只输出一个 JSON 数组，不要输出任何其他内容
2. 每个元素格式：{{"title": "图表标题", "display_type": "图表类型", \
"thought": "一句话说明该图表达的观点"{sql_hint}}}
3. 图表数量不超过 {max_charts} 张，优先选择最能说明问题的图表

用户问题：
{user_input}

分析结论：
{analysis}

数据样例：
{data_report}"""

_DEFAULT_CHART_PROMPT_EN = """You are a data visualization expert. Design at most \
{max_charts} charts based on the user question, analysis and data.

Available chart types:
{display_type}

{data_hint}

Requirements:
1. Output ONLY a JSON array, nothing else
2. Each item: {{"title": "chart title", "display_type": "chart type", \
"thought": "one sentence about the insight"{sql_hint}}}
3. At most {max_charts} charts, pick the most informative ones

User question:
{user_input}

Analysis:
{analysis}

Data sample:
{data_report}"""

_SQL_HINT_ZH = ', "sql": "查询该图数据的 SQL（必须，基于数据库表结构生成）"'
_SQL_HINT_EN = ', "sql": "SQL to fetch chart data (required, based on db schema)"'
_COL_HINT_ZH = ', "columns": ["需要从数据中选取的列名"]'
_COL_HINT_EN = ', "columns": ["columns to pick from the dataset"]'


class HOChartAdvisorOperator(GPTVisMixin, MixinLLMOperator, JoinOperator[str]):
    """Propose charts via LLM and render a dashboard with gpt-vis."""

    metadata = ViewMetadata(
        label=_("TaskFlow Chart Advisor Operator"),
        name="taskflow_chart_advisor_operator",
        description=_("Propose charts via LLM and render a dashboard."),
        category=OperatorCategory.DATABASE,
        parameters=[
            Parameter.build_from(
                _("Datasource"),
                "datasource",
                DBResource,
                optional=True,
                default=None,
                description=_(
                    "The datasource used to execute chart SQL. If empty, charts "
                    "are built from the upstream dataset."
                ),
            ),
            Parameter.build_from(
                _("Model Name"),
                "model",
                str,
                optional=True,
                default=None,
                description=_("The model name."),
            ),
            Parameter.build_from(
                _("LLM Client"),
                "llm_client",
                LLMClient,
                optional=True,
                default=None,
                description=_("The LLM client, use the default client if empty."),
            ),
            Parameter.build_from(
                _("Max Charts"),
                "max_charts",
                int,
                optional=True,
                default=4,
                description=_("The maximum number of charts to generate."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("User question"),
                "question",
                str,
                description=_("The analysis objective from the user."),
            ),
            IOField.build_from(
                _("Analysis context"),
                "analysis_context",
                str,
                description=_("Upstream analysis conclusions and data."),
                dynamic=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Dashboard view"),
                "dashboard_view",
                str,
                description=_("The rendered dashboard view (gpt-vis format)."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        datasource: Optional[DBResource] = None,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        max_charts: int = 4,
        **kwargs,
    ):
        JoinOperator.__init__(self, combine_function=self._join_func, **kwargs)
        MixinLLMOperator.__init__(self, llm_client=llm_client, **kwargs)
        self._datasource = datasource
        self._model = model
        self._max_charts = max_charts

    async def _join_func(self, question: str, *args) -> str:
        parts = [strip_step_markers(a) for a in args if isinstance(a, str) and a]
        context = "\n\n".join(p for p in parts if p)
        language = (
            self.system_app.config.get_current_lang() if self.system_app else "zh"
        )
        has_db = self._datasource is not None
        if has_db:
            schema_info = await self.blocking_func_to_async(
                self._datasource.get_schema_link,
                db=self._datasource._db_name,
                question=question,
            )
            data_hint = (
                f"数据库表结构：\n{schema_info}"
                if language == "zh"
                else f"Database schema:\n{schema_info}"
            )
            sql_hint = _SQL_HINT_ZH if language == "zh" else _SQL_HINT_EN
        else:
            df = await self.current_dag_context.get_from_share_data(
                SHARE_KEY_TASKFLOW_FILE_DF
            )
            if df is not None:
                cols = ", ".join(str(c) for c in df.columns)
                data_hint = (
                    f"数据集列名：{cols}（图表将基于该数据集生成，无需 SQL）"
                    if language == "zh"
                    else f"Dataset columns: {cols} (charts are built from this "
                    "dataset, no SQL needed)"
                )
            else:
                data_hint = (
                    "无可用数据库，图表将基于上文数据生成，无需 SQL"
                    if language == "zh"
                    else "No database available, build charts from the data above."
                )
            sql_hint = _COL_HINT_ZH if language == "zh" else _COL_HINT_EN
        template = (
            _DEFAULT_CHART_PROMPT_ZH if language == "zh" else _DEFAULT_CHART_PROMPT_EN
        )
        prompt = template.format(
            max_charts=self._max_charts,
            display_type=default_chart_type_prompt(),
            data_hint=data_hint,
            sql_hint=sql_hint,
            user_input=question,
            analysis=context[:4000],
            data_report=context[-4000:],
        )
        models = await self.llm_client.models()
        if not models:
            raise Exception("No models available.")
        model = self._model or models[0].model
        messages = ModelMessage.from_base_messages(
            ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template("{input}")]
            ).format_messages(input=prompt)
        )
        model_output = await self.llm_client.generate(
            ModelRequest.build_request(model, messages=messages)
        )
        # Content-only first: reasoning text is full of inline brackets
        # that used to break the array slice; fall back to the
        # thinking-included concatenation, then to one strict retry.
        proposals = self._extract_json_array(model_output.text or "")
        if not proposals:
            proposals = self._extract_json_array(model_output.gen_text_with_thinking())
        if not proposals:
            strict_suffix = (
                "\n\n【强制】上一次回复无法解析为 JSON 数组。这次只输出 JSON "
                "数组本身：不要推理过程、不要代码围栏、不要任何额外文字。"
                if language == "zh"
                else "\n\n[STRICT] Your previous reply could not be parsed as a "
                "JSON array. This time output ONLY the JSON array itself: no "
                "reasoning, no code fences, no extra text."
            )
            retry_output = await self.llm_client.generate(
                ModelRequest.build_request(
                    model,
                    messages=ModelMessage.from_base_messages(
                        ChatPromptTemplate(
                            messages=[HumanPromptTemplate.from_template("{input}")]
                        ).format_messages(input=prompt + strict_suffix)
                    ),
                )
            )
            proposals = self._extract_json_array(
                (retry_output.text or "") + retry_output.gen_text_with_thinking()
            )
        if not proposals:
            # Fail loudly: an empty string here used to surface as a
            # "success" node with no dashboard and no explanation.
            raise Exception(
                "chart advisor returned no parseable chart proposals "
                "(expected a JSON array of {title, display_type, thought, "
                "columns})"
            )
        return await self._render_dashboard(question, proposals[: self._max_charts])

    @staticmethod
    def _extract_json_array(text: str) -> List[dict]:
        """Parse the chart-proposal JSON array tolerantly.

        Reasoning models surround the array with prose that itself
        contains brackets (``columns ["Date","Weekly_Sales"]``), so the
        naive ``find('[')``/``rfind(']')`` slice yields invalid JSON and
        the node silently produced nothing. Scan every ``'['`` from the
        last backwards with string-aware bracket matching and return the
        first parseable object-array.
        """
        if not text:
            return []
        for start in reversed([i for i, ch in enumerate(text) if ch == "["]):
            depth = 0
            in_str = False
            esc = False
            for j in range(start, len(text)):
                ch = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            value = json.loads(text[start : j + 1])
                        except (ValueError, TypeError):
                            break
                        if isinstance(value, list):
                            dicts = [p for p in value if isinstance(p, dict)]
                            if dicts:
                                return dicts
                        break
        return []

    @staticmethod
    def _parse_proposals(text: str) -> List[dict]:
        """Parse the chart proposals JSON array from the LLM output."""
        return HOChartAdvisorOperator._extract_json_array(text)

    async def _render_dashboard(self, question: str, proposals: List[dict]) -> str:
        from dbgpt.vis.tags.vis_dashboard import VisDashboard

        chart_params = []
        shared_df = None
        if self._datasource is None:
            shared_df = await self.current_dag_context.get_from_share_data(
                SHARE_KEY_TASKFLOW_FILE_DF
            )
        for item in proposals:
            chart_dict = {
                "title": item.get("title", ""),
                "display_type": item.get("display_type", "response_table"),
                "thought": item.get("thought", ""),
                "sql": item.get("sql", "") or "",
            }
            try:
                if self._datasource is not None and chart_dict["sql"]:
                    chart_dict["data"] = await self._datasource.query_to_df(
                        chart_dict["sql"]
                    )
                elif shared_df is not None:
                    columns = item.get("columns") or list(shared_df.columns)
                    valid_columns = [c for c in columns if c in shared_df.columns]
                    chart_dict["data"] = (
                        shared_df[valid_columns] if valid_columns else shared_df
                    )
                else:
                    chart_dict["err_msg"] = "No data available for chart"
            except Exception as e:
                logger.warning(f"TaskFlow chart data build failed: {e}")
                chart_dict["err_msg"] = str(e)
            chart_params.append(chart_dict)
        vis = VisDashboard()
        view = await vis.display(charts=chart_params)
        await self.save_view_message(self.current_dag_context, view)
        return view


# ---------------------------------------------------------------------------
# Human confirm operator (P0: soft confirm, ordering + step marker only)
# ---------------------------------------------------------------------------


class HOHumanConfirmOperator(MapOperator[str, str]):
    """Human confirmation node.

    P0 implements a *soft* confirmation: the operator preserves execution
    order (downstream nodes depending on it will run after) and emits a step
    marker, but does not pause the DAG. Real pause/resume via the conversation
    HITL channel lands in P1.
    """

    metadata = ViewMetadata(
        label=_("TaskFlow Human Confirm Operator"),
        name="taskflow_human_confirm_operator",
        description=_("Pause the flow and wait for human confirmation."),
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(
                _("Confirm Message"),
                "message",
                str,
                optional=True,
                default="请确认上一步结果后继续",
                description=_("The message shown to the user for confirmation."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Upstream content"),
                "upstream_content",
                str,
                description=_("The upstream content (for ordering only)."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Pass-through"),
                "pass_through",
                str,
                description=_("Empty pass-through output."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, message: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._message = message or "请确认上一步结果后继续"

    async def map(self, upstream_content: str) -> str:
        """Pass through (P0 soft confirm)."""
        return ""
