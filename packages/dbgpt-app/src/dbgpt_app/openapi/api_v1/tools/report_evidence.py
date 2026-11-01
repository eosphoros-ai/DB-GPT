"""Expose captured execution artifacts to the HTML report author."""

import hashlib
import json
from collections import Counter
from typing import Any, Dict, Optional

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report import (
    ChartArtifact,
    PythonArtifact,
    ReferenceArtifact,
    SQLArtifact,
    normalize_result_selector,
)
from dbgpt.core.interface.report_capture import (
    get_current_artifact_sink,
    read_artifact_result,
    select_artifact_result,
    select_result_value,
)

_MANIFEST_SQL_ROWS = 3
_MANIFEST_TEXT_CHARS = 360
_MANIFEST_KB_EXCERPT_CHARS = 900
_MANIFEST_RESULT_CHARS = 3000
_MANIFEST_DETAIL_LIMIT = 12


def result_structure(value, depth=0, budget=256):
    """Expose keys and array sizes independently of a truncated value preview."""
    if depth >= 8 or budget <= 0:
        if isinstance(value, dict):
            return {"type": "object", "keys": list(value)[:30], "truncated": True}
        if isinstance(value, list):
            return {"type": "array", "length": len(value), "truncated": True}
        return "null" if value is None else type(value).__name__
    if isinstance(value, dict):
        items = list(value.items())[:30]
        share = (budget - 1) // max(len(items), 1)
        return {key: result_structure(child, depth + 1, share) for key, child in items}
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "sample_items": [
                result_structure(
                    child, depth + 1, (budget - 1) // max(min(len(value), 3), 1)
                )
                for child in value[:3]
            ],
        }
    return "null" if value is None else type(value).__name__


def result_selector_context(artifact, selector):
    """Describe the actual container where a selector stopped resolving."""
    selector = normalize_result_selector(selector)
    value = read_artifact_result(artifact)
    field = selector.get("field")
    if field is not None:
        value = select_result_value(value, {"field": field})
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        value = json.loads(value)
    prefix = []
    for key in selector.get("path") or []:
        try:
            value = select_result_value(value, {"path": [key]})
        except (ValueError, TypeError):
            break
        prefix.append(key)
    examples = []

    def visit(item, path, depth=0):
        if len(examples) >= 12 or depth > 5:
            return
        if isinstance(item, dict):
            for key, child in list(item.items())[:20]:
                visit(child, [*path, key], depth + 1)
        elif isinstance(item, list):
            for index, child in enumerate(item[:3]):
                visit(child, [*path, index], depth + 1)
        elif isinstance(item, (str, int, float)) and not isinstance(item, bool):
            examples.append(
                {
                    "selector": {**({"field": field} if field else {}), "path": path},
                    "value": item[:160] if isinstance(item, str) else item,
                }
            )

    visit(value, prefix)
    return {
        "resolved_prefix": prefix,
        "actual_structure": result_structure(value),
        "valid_references": examples,
    }


def _bounded_result_preview(value):
    """Bound nested Python output, including inspection of old checkpoints."""
    remaining = _MANIFEST_RESULT_CHARS
    truncated = False

    def visit(item, depth=0):
        nonlocal remaining, truncated
        if remaining <= 0 or depth > 5:
            truncated = True
            return None
        if isinstance(item, dict):
            preview = {}
            for index, (key, child) in enumerate(item.items()):
                if index >= 25 or remaining <= 0:
                    truncated = True
                    break
                if len(str(key)) + 8 > remaining:
                    truncated = True
                    break
                remaining -= len(str(key)) + 8
                preview[key] = visit(child, depth + 1)
            return preview
        if isinstance(item, list):
            preview = []
            for index, child in enumerate(item):
                if index >= 6 or remaining <= 0:
                    truncated = True
                    break
                remaining -= 2
                preview.append(visit(child, depth + 1))
            return preview
        if isinstance(item, str):
            limit = min(_MANIFEST_TEXT_CHARS, max(remaining, 0))
            truncated = truncated or len(item) > limit
            remaining -= min(len(item), limit) + 2
            return item[:limit]
        remaining -= len(str(item)) + 2
        return item

    return visit(value), truncated


def _compact_sql_preview(value: Any, max_rows: int = _MANIFEST_SQL_ROWS) -> Any:
    """Keep the evidence manifest actionable instead of flooding the report LLM."""
    if not isinstance(value, dict):
        return value
    preview = dict(value)
    rows = preview.get("rows")
    if isinstance(rows, list) and len(rows) > max_rows:
        preview["rows"] = rows[:max_rows]
        preview["rows_omitted"] = len(rows) - max_rows
    return preview


def _artifact_manifest_item(
    artifact: Any,
    execution_step_map: Dict[str, str] | None = None,
    *,
    detail: bool = False,
) -> Dict[str, Any]:
    """Serialize the discriminated artifact union without cross-type access."""
    item: Dict[str, Any] = {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "name": artifact.name,
        "status": artifact.status,
        "action": artifact.execution.action,
        "step_id": (execution_step_map or {}).get(
            artifact.execution.step_id, artifact.execution.step_id
        ),
        "input_artifact_ids": list(artifact.input_artifact_ids),
        "agent_id": artifact.metadata.get("agent_id"),
        "agent_name": artifact.metadata.get("agent_name"),
    }
    if isinstance(artifact, SQLArtifact):
        item.update(
            {
                "database": artifact.database,
                "columns": artifact.columns[:25],
                "row_count": artifact.row_count,
                "result_selector_examples": [
                    {"path": ["rows", 0, column]} for column in artifact.columns[:1]
                ]
                if artifact.row_count
                else [],
                "result_preview": _compact_sql_preview(
                    artifact.result.inline if artifact.result is not None else None,
                    max_rows=50 if detail else _MANIFEST_SQL_ROWS,
                ),
            }
        )
        if detail:
            item["sql"] = artifact.sql
    elif isinstance(artifact, PythonArtifact):
        result = artifact.result.inline if artifact.result is not None else None
        if detail and artifact.result is not None:
            result = read_artifact_result(artifact)
        preview_data = result
        if isinstance(result, dict):
            preview_data = dict(result)
            for field, value in result.items():
                if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
                    try:
                        preview_data[field] = json.loads(value)
                    except ValueError:
                        pass
        preview, truncated = _bounded_result_preview(preview_data)
        examples = []
        if isinstance(preview_data, dict):
            for field, value in preview_data.items():
                examples.extend(
                    [{"field": field, "path": [key]} for key in list(value)[:12]]
                    if isinstance(value, dict)
                    else [{"field": field, "path": []}]
                )
        item.update(
            {
                "language": artifact.language,
                "exit_code": artifact.exit_code,
                "result_structure": result_structure(preview_data),
                "result_preview": preview,
                "result_preview_truncated": truncated,
                "stdout_preview": (artifact.stdout or "")[:_MANIFEST_TEXT_CHARS],
                "result_selector_examples": examples[:25],
            }
        )
    elif isinstance(artifact, ChartArtifact):
        item.update(
            {
                "chart_type": artifact.chart_type,
                "output_uri": (
                    artifact.output.uri if artifact.output is not None else None
                ),
            }
        )
    elif isinstance(artifact, ReferenceArtifact):
        excerpt_limit = (
            _MANIFEST_KB_EXCERPT_CHARS
            if artifact.reference_type == "knowledge"
            else _MANIFEST_TEXT_CHARS
        )
        item.update(
            {
                "reference_type": artifact.reference_type,
                "source_id": artifact.source_id,
                "source_name": artifact.source_name,
                "uri": artifact.uri,
                "locator": artifact.locator,
                "excerpt": (artifact.excerpt or "")[:excerpt_limit],
                "retrieval_query": artifact.metadata.get("retrieval_query"),
                "retrieval_rank": artifact.metadata.get("retrieval_rank"),
                "retrieval_score": artifact.score,
            }
        )
    return item


def result_evidence_catalog(artifacts) -> list[dict]:
    """Reuse the manifest's result contract for actionable rendering diagnostics."""
    keys = (
        "artifact_id",
        "type",
        "agent_name",
        "columns",
        "row_count",
        "result_selector_examples",
    )
    return [
        {
            key: value
            for key, value in _artifact_manifest_item(artifact).items()
            if key in keys and value is not None
        }
        for artifact in artifacts
        if artifact.status == "succeeded" and artifact.type in {"sql", "python"}
    ]


def make_report_evidence_manifest(react_state: Optional[Dict[str, Any]] = None):
    # A new report agent has new memory even when it shares the lead's state.
    # Cache reuse is safe only after this particular tool consumer saw the catalog.
    delivered_revisions: set[str] = set()

    @tool(
        description=(
            "Return the executed artifacts that may be cited by a final HTML report. "
            "Call this immediately before html_interpreter when creating an analysis "
            "report. For every KPI, chart, table, or conclusion that uses an artifact, "
            'add data-dbgpt-artifacts="artifact-id[,artifact-id]" to its containing '
            "HTML element and add a concise data-dbgpt-evidence-label. Wrap numeric "
            "claims in strong/span elements so each number is independently clickable. "
            "If a retrieved KB rule governs a metric, cite its precise reference "
            "artifact on that metric container; cite SQL/Python on the numeric value. "
            "Choose the reference artifact by its exact excerpt and locator (chunk, "
            "page, or matched line range); do not infer a KB citation from similar "
            "words or reuse a whole-document read. Keep each KB reference on the "
            "specific governed block that uses it. kb_cat preserves one reference "
            "per source chunk, including full-file reads. Select only the chunk(s) "
            "that contain the governing rule; do not attach every returned chunk. "
            "Use kb_cat(path, chunk_id) to inspect a specific retrieved chunk. "
            "Optionally, on that same element, provide "
            "data-dbgpt-artifact-selectors as a JSON object mapping each KB artifact "
            "ID to a verbatim quote from that artifact's excerpt, for example "
            '{"reference-id":{"quote":"exact source sentence"}}. The renderer '
            "validates and persists the quote with the source locator. "
            "Figure or table numbers such as 图1 are labels, not numeric claims. "
            "Never invent an artifact id or bind an unsupported claim. If status is "
            "empty or an error, do not repeat successful analysis work; report the "
            "capture problem."
            " Pass artifact_ids to fetch only the evidence needed for a block; "
            "the default is a compact catalog. Unchanged selections reuse manifest_id. "
            "quote is optional for chunk bindings; validate it only when provided. "
            "Use existing template_path/data for a long HTML report."
        )
    )
    async def report_evidence_manifest(
        artifact_ids: list[str] | None = None,
        artifact_types: list[str] | None = None,
        detail: bool = False,
        force_refresh: bool = False,
        selectors: dict[str, dict] | None = None,
    ) -> str:
        """List bounded artifact identifiers captured earlier in this turn."""
        # Normal report capture lives in a context variable, so this tool is
        # reusable by any Agent implementation.  ``react_state`` remains a
        # compatibility fallback for old callers and tests.
        state = react_state if react_state is not None else {}
        state["_report_render_phase"] = True
        # Report recovery can replace the turn's sink after the context variable
        # was installed. The shared report state owns that restored/new evidence.
        sink = state.get("_report_artifact_sink") or get_current_artifact_sink()
        if sink is None:
            return json.dumps(
                {
                    "status": "capture_unavailable",
                    "artifacts": [],
                    "diagnostics": {
                        "message": (
                            "No artifact sink is attached to this turn. Do not rerun "
                            "successful analysis steps."
                        ),
                    },
                },
                ensure_ascii=False,
            )
        try:
            artifacts = sink.snapshot()
        except Exception as error:
            return json.dumps(
                {
                    "status": "manifest_error",
                    "artifacts": [],
                    "diagnostics": {
                        "message": str(error) or type(error).__name__,
                        "capture_run_id": getattr(sink.context, "run_id", None),
                    },
                },
                ensure_ascii=False,
            )

        captured_count = len(artifacts)
        requested = set(artifact_ids or (selectors or {}).keys())
        unknown = requested - {artifact.artifact_id for artifact in artifacts}
        if unknown:
            return json.dumps(
                {"status": "unknown_artifact_ids", "artifact_ids": sorted(unknown)},
                ensure_ascii=False,
            )
        artifacts = [
            artifact
            for artifact in artifacts
            if artifact.status == "succeeded"
            and (not requested or artifact.artifact_id in requested)
            and (not artifact_types or artifact.type in artifact_types)
        ]
        execution_step_map = state.get("_report_execution_step_map", {})
        detailed = (detail or bool(requested)) and len(
            artifacts
        ) <= _MANIFEST_DETAIL_LIMIT
        items = [
            _artifact_manifest_item(artifact, execution_step_map, detail=detailed)
            for artifact in artifacts
        ]
        if selectors:
            by_id = {item.artifact_id: item for item in artifacts}
            if not detailed or set(selectors) - set(by_id):
                return json.dumps(
                    {
                        "status": "selector_invalid",
                        "error": (
                            "Select at most 12 real SQL/Python artifact IDs; "
                            "each selector "
                            "ID must be in the returned "
                            "selection."
                        ),
                    }
                )
            for item in items:
                artifact_id = item["artifact_id"]
                if artifact_id not in selectors:
                    continue
                try:
                    selector = normalize_result_selector(selectors[artifact_id])
                    value = select_artifact_result(by_id[artifact_id], selector)
                    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
                        value = json.loads(value)
                    preview, truncated = _bounded_result_preview(value)
                    item.update(
                        result_preview=preview,
                        result_preview_truncated=truncated,
                        selected_result=selector,
                        available_selected_keys=list(value)[:25]
                        if isinstance(value, dict)
                        else [],
                    )
                except (ValueError, TypeError, OSError) as error:
                    return json.dumps(
                        {
                            "status": "selector_invalid",
                            "artifact_id": artifact_id,
                            "selector": selectors[artifact_id],
                            "error": str(error),
                        },
                        ensure_ascii=False,
                    )
        revision = hashlib.sha256(
            json.dumps(
                {
                    "artifacts": items,
                    "step_map": {
                        artifact.execution.step_id: execution_step_map.get(
                            artifact.execution.step_id, artifact.execution.step_id
                        )
                        for artifact in artifacts
                    },
                    "detail": detailed,
                },
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ).encode()
        ).hexdigest()[:20]
        cache = state.setdefault("_report_manifest_cache", {})
        if (
            revision in cache
            and revision in delivered_revisions
            and not force_refresh
            and not detailed
        ):
            return json.dumps(
                {
                    "status": "unchanged",
                    "manifest_id": revision,
                    "artifact_ids": [a.artifact_id for a in artifacts],
                    "usage": (
                        "Reuse this manifest's previous evidence. Request specific "
                        "artifact_ids or force_refresh=true if needed."
                    ),
                },
                ensure_ascii=False,
            )
        if not detailed:
            for item in items:
                item.pop("result_preview", None)
                item.pop("stdout_preview", None)
                excerpt = item.pop("excerpt", None)
                if excerpt:
                    item["excerpt_preview"] = excerpt[:160]
        cache[revision] = True
        delivered_revisions.add(revision)
        retrieval_groups: Dict[str, Dict[str, Any]] = {}
        for item in items:
            if item.get("reference_type") != "knowledge":
                continue
            query = item.get("retrieval_query") or "未记录检索词"
            group = retrieval_groups.setdefault(
                query, {"query": query, "candidate_artifact_ids": []}
            )
            group["candidate_artifact_ids"].append(item["artifact_id"])
        counts = Counter(artifact.type for artifact in artifacts)
        succeeded = [item for item in items if item.get("status") == "succeeded"]
        chart_items = [item for item in succeeded if item.get("type") == "chart"]
        python_items = [item for item in succeeded if item.get("type") == "python"]
        sql_items = [item for item in succeeded if item.get("type") == "sql"]
        examples = []
        if sql_items:
            sql_id = sql_items[0]["artifact_id"]
            examples.append(
                {
                    "object": "one SQL-backed KPI or table",
                    "html": (
                        f'<section data-dbgpt-artifacts="{sql_id}" '
                        'data-dbgpt-evidence-label="指标名称">'
                        f'<strong data-dbgpt-artifacts="{sql_id}">数值</strong>'
                        "</section>"
                    ),
                }
            )
        if chart_items:
            chart = chart_items[0]
            related_ids = [*chart.get("input_artifact_ids", []), chart["artifact_id"]]
            # A Python artifact may itself declare the SQL inputs that made the
            # chart.  Include those in the figure's *single* local binding.
            for python in python_items:
                if python["artifact_id"] in related_ids:
                    related_ids = [*python.get("input_artifact_ids", []), *related_ids]
            ids = ",".join(dict.fromkeys(related_ids))
            examples.append(
                {
                    "object": "the matching generated chart only",
                    "html": (
                        f'<figure data-dbgpt-artifacts="{ids}" '
                        'data-dbgpt-evidence-label="图表名称">'
                        f'<img src="{chart.get("output_uri") or "图表URL"}"></figure>'
                    ),
                }
            )
        if sql_items and "rows" in (sql_items[0].get("result_preview") or {}):
            sql_id = sql_items[0]["artifact_id"]
            selectors = json.dumps({sql_id: {"field": "rows"}})
            examples.append(
                {
                    "object": "existing ECharts template host using SQL rows",
                    "html": (
                        '<figure data-dbgpt-chart-renderer="echarts" '
                        'data-dbgpt-block-id="sql-chart-figure" '
                        f'data-dbgpt-artifacts="{sql_id}" '
                        f"data-dbgpt-artifact-selectors='{selectors}'>"
                        '<div id="sql-chart" class="chart-box" '
                        'style="height:320px"></div>'
                        "</figure>"
                    ),
                    "usage": (
                        "Use echarts.init(document.getElementById('sql-chart')) and "
                        "setOption with the exact captured rows. The renderer captures "
                        "this chart and supplies its ChartArtifact ID; "
                        "do not invent an ID."
                    ),
                }
            )
        return json.dumps(
            {
                "status": "ok" if artifacts else "empty",
                "manifest_id": revision,
                "artifacts": items,
                "knowledge_retrievals": list(retrieval_groups.values()),
                "diagnostics": {
                    "capture_run_id": getattr(sink.context, "run_id", None),
                    "captured_count": captured_count,
                    "returned_count": len(items),
                    "counts_by_type": dict(sorted(counts.items())),
                    "truncated": any(
                        item.get("result_preview_truncated") for item in items
                    ),
                    "detail_requires_selection": (detail or bool(requested))
                    and not detailed,
                },
                "usage": (
                    "For detailed results, select at most 12 artifact_ids per call. "
                    "Nested result previews are bounded; full results remain in "
                    "their captured artifacts. "
                    "Use only the compact artifact list above. Make a concise report "
                    "with 3–6 visible KPI/table/chart objects, not one object per "
                    "artifact. Every visible data object needs its own local binding; "
                    "every conclusion number needs its own strong binding. Empty or "
                    "error status is a capture problem; do not repeat successful SQL "
                    "or Python work to manufacture artifacts."
                ),
                "binding_examples": examples,
            },
            ensure_ascii=False,
        )

    return report_evidence_manifest
