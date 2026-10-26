"""html_interpreter tool — render HTML as an interactive report."""

import ast
import asyncio
import hashlib
import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from html import escape as escape_html
from html import unescape as unescape_html
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report_capture import (
    normalize_artifact_result_selector,
    read_artifact_result,
    select_artifact_result,
    sql_predicate_quotes,
)
from dbgpt.core.interface.report_html import normalize_report_html

from .report_binding import (
    EVIDENCE_TAG_PATTERN,
    BindingAttributeError,
    capture_template_charts,
    claim_target_texts,
    html_tokens,
    is_document_number,
    iter_binding_tags,
    normalize_binding_attributes,
    normalize_payload_selectors,
    parse_binding,
    replace_binding_tags,
    validate_knowledge_sources,
    validate_report_targets,
    validate_result_selectors,
    validate_template_fragment,
)
from .report_evidence import result_evidence_catalog, result_selector_context
from .report_policy import DEFAULT_TRACEABLE_REPORT_POLICY
from .report_repair import report_repair_guard, retain_html_candidate
from .report_spec import report_data_schema, validate_report_spec

logger = logging.getLogger(__name__)


def _validate_complete_html_document(html: str) -> str | None:
    """Reject partial HTML instead of persisting a misleading rendered report.

    A ReAct response can be cut off while it is still writing the ``html``
    argument.  Browsers make a best effort to display that fragment, which used
    to let ``html_interpreter`` announce success even though the stored report
    was missing the end of a chart/card (and often the closing document tags).
    Root/body closing tags are a deliberately small, deterministic completeness
    gate that does not attempt to reimplement an HTML parser.
    """
    normalized = html.strip().lower()
    checks = {
        "html_open": r"<html(?:\s|>)",
        "body_open": r"<body(?:\s|>)",
        "body_close": r"</body\s*>",
        "html_close": r"</html\s*>\s*$",
    }
    missing = [
        name for name, pattern in checks.items() if not re.search(pattern, normalized)
    ]
    if missing:
        anchor = html[-240:]
        # Find a unique suffix suitable for the existing exact replacement API.
        while anchor and html.count(anchor) != 1 and len(anchor) < len(html):
            anchor = html[-min(len(html), len(anchor) + 240) :]
        return (
            "HTML_DOCUMENT_INCOMPLETE: "
            "missing="
            f"{','.join(missing)}"
            "; HTML length="
            f"{len(html)}"
            ", "
            "tail offset="
            f"{len(html) - len(anchor)}"
            "; tail_anchor="
            f"{json.dumps(anchor, ensure_ascii=False)}"
            ". "
            "The candidate has been saved. Use retry_saved=true with repair_patches "
            "to replace this exact tail anchor with the anchor plus the missing report "
            "content and closing body/html tags. Preserve existing artifact IDs and "
            "all requested sections. Do not regenerate the full HTML or rerun analysis."
        )
    return None


def _validate_recommendation_requirement(
    html: str, required_count: int | None
) -> str | None:
    """Ensure an explicitly requested recommendation count reaches the report.

    This is intentionally a narrow delivery-completeness check, not a content
    quality scorer.  The model may choose the recommendation wording and style,
    but a user who explicitly asks for a fixed number of actionable
    recommendations must not receive a persisted report that silently omits
    that requested section.
    """
    if not isinstance(required_count, int) or required_count < 1:
        return None

    headings = list(
        re.finditer(
            r"<h[1-6]\b[^>]*>(.*?)</h[1-6]\s*>", html, re.IGNORECASE | re.DOTALL
        )
    )
    found_count = 0
    counted_until = -1
    for index, heading in enumerate(headings):
        if heading.start() < counted_until:
            continue
        heading_text = re.sub(r"<[^>]+>", " ", heading.group(1))
        heading_text = " ".join(unescape_html(heading_text).split()).lower()
        if "建议" not in heading_text and "recommend" not in heading_text:
            continue
        level = int(heading.group(0)[2])
        section_end = next(
            (
                following.start()
                for following in headings[index + 1 :]
                if int(following.group(0)[2]) <= level
            ),
            len(html),
        )
        section = html[heading.end() : section_end]
        counted_until = section_end
        items = re.findall(
            r"<li\b[^>]*>(.*?)</li\s*>", section, re.IGNORECASE | re.DOTALL
        )
        actionable_items = [
            " ".join(unescape_html(re.sub(r"<[^>]+>", " ", item)).split())
            for item in items
        ]
        count = len([item for item in actionable_items if item])
        # Cards commonly place their ordinal in a separate div and their action
        # in a plain h3. Count sibling action headings, excluding nested detail
        # headings; their wording need not repeat "建议 1" or "P1".
        subheadings = [
            (int(match[1]), unescape_html(re.sub(r"<[^>]+>", " ", match[2])).strip())
            for match in re.finditer(
                r"<h([1-6])\b[^>]*>(.*?)</h\1\s*>", section, re.I | re.S
            )
            if int(match[1]) > level
        ]
        if subheadings:
            action_level = min(rank for rank, text in subheadings)
            count = max(
                count,
                sum(rank == action_level and bool(text) for rank, text in subheadings),
            )
        # Numbered recommendation cards and subheadings are valid report
        # content. Do not force a model to duplicate them into an ordered list.
        labels = re.findall(
            r"<(?:strong|b|h[3-6])\b[^>]*>\s*"
            r"(?:建议\s*([0-9一二三四五六七八九十]+)|"
            r"P\s*([0-9]+)|(?:recommendation|priority)\s*([0-9]+))"
            r"(?=\s|[：:、.．—-]|[^0-9A-Za-z])",
            section,
            re.I,
        )
        numbered = {next(value for value in label if value) for label in labels}
        found_count += max(count, len(numbered))
        if found_count >= required_count:
            return None

    return (
        "REPORT_REQUIREMENT_MISSING: The user explicitly requested "
        f"{required_count} actionable recommendation(s), but the HTML does not "
        f"contain that many items under recommendation sections (found={found_count}; "
        f"missing={required_count - found_count}). Add the missing "
        "concrete actions as list items, numbered cards or recommendation "
        "subheadings; preserve existing recommendations. Bind numeric "
        "claims to their actual "
        "evidence, and retry html_interpreter without rerunning completed analysis."
    )


def _validate_evidence_bindings(
    html: str,
    artifact_ids: List[str],
    required_artifact_ids: List[str] | None = None,
    required_native_chart_artifact_ids: List[str] | None = None,
    artifact_types: Dict[str, str] | None = None,
    artifacts: List[Any] | None = None,
) -> str | None:
    """Return a retry message when a data-backed report has no valid bindings."""
    available_ids = {str(value).strip() for value in artifact_ids if str(value).strip()}
    try:
        parsed_bindings = [parse_binding(match) for match in iter_binding_tags(html)]
    except BindingAttributeError as error:
        return str(error)
    bindings = [",".join(binding["artifact_ids"]) for binding in parsed_bindings]
    referenced_ids = {
        item.strip()
        for binding in bindings
        for item in binding.split(",")
        if item.strip()
    }
    unknown_ids = referenced_ids - available_ids
    if unknown_ids:
        bad = next(
            binding
            for binding in parsed_bindings
            if set(binding["artifact_ids"]) & unknown_ids
        )
        return (
            "TRACEABILITY_BINDING_INVALID: attribute=data-dbgpt-artifacts; "
            "container="
            f"{bad['container']}"
            "; unknown artifact IDs: "
            f"{', '.join(sorted(unknown_ids))}"
        )
    chart_target_error = validate_report_targets(
        html,
        artifact_types or {},
        numeric_pattern=_NUMERIC_CLAIM_PATTERN,
        numeric_skip_tags=_NUMERIC_CLAIM_SKIP_TAGS,
        non_metric_prefix=_NON_METRIC_NUMBER_PREFIX,
        numeric_evidence=_numeric_evidence_validator(artifacts)
        if artifacts is not None
        else None,
        chart_evidence=_chart_evidence_validator(artifacts)
        if artifacts is not None
        else None,
    )
    if chart_target_error:
        return chart_target_error
    if not bindings and available_ids:
        return (
            "TRACEABILITY_BINDING_REQUIRED: This report uses executed artifacts but "
            "contains no object-level evidence binding. Call report_evidence_manifest "
            "and retry html_interpreter. Put real artifact IDs on EACH KPI/card/chart "
            "container and wrap EACH numeric claim in a conclusion with a separate "
            '<strong data-dbgpt-artifacts="..."> value </strong>. Do not bind all '
            "artifacts to every element."
        )
    # A table is already a data presentation.  Binding a ChartArtifact to it
    # makes the UI advertise a chart where there is none ("SQL · chart"), and
    # makes the evidence drawer misleading.  A chart must be bound to the
    # actual figure/image/chart container that renders it instead.  This is a
    # semantic constraint only: it does not alter DB-GPT's generated markup or
    # report styling.
    chart_ids = {
        artifact_id
        for artifact_id, artifact_type in (artifact_types or {}).items()
        if artifact_type == "chart"
    }
    for match in iter_binding_tags(html):
        if match.group("tag").lower() != "table":
            continue
        bound_chart_ids = {
            item.strip()
            for item in parse_binding(match)["artifact_ids"]
            if item.strip() in chart_ids
        }
        if bound_chart_ids:
            return (
                "TRACEABILITY_BINDING_INVALID: A <table> is bound to chart "
                f"artifact(s) {', '.join(sorted(bound_chart_ids))}, but it does not "
                "render those charts. Keep only the SQL/Python evidence supporting "
                "the table on <table>; put each ChartArtifact on the separate "
                "<figure>, chart container, or generated <img> that displays it."
            )
    required_ids = set(required_artifact_ids or [])
    missing_required = required_ids - referenced_ids
    if missing_required:
        return (
            "TRACEABILITY_BINDING_REQUIRED: The report embeds generated chart output "
            "but does not cite its chart artifact. Bind the chart image or its "
            "containing figure/section to the real artifact IDs: "
            f"{', '.join(sorted(missing_required))}. Also retain the supporting SQL "
            "artifact on that chart container."
        )
    required_native_chart_ids = set(required_native_chart_artifact_ids or [])
    if required_native_chart_ids:
        figure_chart_ids = {
            item.strip()
            for match in iter_binding_tags(html)
            if match.group("tag").lower() == "figure"
            for item in parse_binding(match)["artifact_ids"]
            if item.strip()
        }
        missing_native_charts = required_native_chart_ids - figure_chart_ids
        if missing_native_charts:
            return (
                "TRACEABILITY_BINDING_REQUIRED: This run generated native chart "
                "artifact(s) that are not rendered in the report: "
                f"{', '.join(sorted(missing_native_charts))}. Add one explicit empty "
                '<figure data-dbgpt-artifacts="supporting-sql,chart-id" '
                'data-dbgpt-evidence-label="chart title"></figure> for each '
                "listed chart. Do not bind chart IDs to a <table>; DB-GPT mounts "
                "native charts only on their own figure containers."
            )
    return None


_EVIDENCE_TAG_PATTERN = EVIDENCE_TAG_PATTERN
_INLINE_EVIDENCE_TAGS = {"strong", "b", "span", "em", "mark", "a"}


def _validate_kb_excerpt_quotes(
    html: str, knowledge_reference_artifacts: Dict[str, Any]
) -> str | None:
    """A captured chunk is sufficient; validate an optional quote when supplied."""
    for match in iter_binding_tags(html):
        try:
            binding = parse_binding(match)
        except BindingAttributeError as error:
            return str(error)
        for artifact_id in set(binding["artifact_ids"]).intersection(
            knowledge_reference_artifacts
        ):
            artifact = knowledge_reference_artifacts[artifact_id]
            if not _is_precise_knowledge_reference(artifact):
                return (
                    "KB_CHUNK_IDENTITY_INVALID: attribute=data-dbgpt-artifacts; "
                    f"container={binding['container']}; artifact={artifact_id}; "
                    "expected a captured document_id and canonical chunk_id with "
                    "source "
                    "text"
                )
            quote = binding["artifact_selectors"].get(artifact_id, {}).get("quote")
            if quote is None:
                continue
            excerpt = getattr(artifact, "excerpt", "") or ""
            # Preserve letter case and punctuation: a quote must be source text.
            normalized_excerpt = re.sub(r"\s+", " ", excerpt).strip()
            normalized_quote = re.sub(r"\s+", " ", quote).strip()
            if normalized_quote not in normalized_excerpt:
                return (
                    "KB_QUOTE_NOT_IN_SOURCE: attribute=data-dbgpt-artifact-selectors; "
                    "container="
                    f"{binding['container']}"
                    "; JSON path "
                    "$."
                    f"{artifact_id}"
                    ".quote; "
                    "select text from this artifact's captured excerpt"
                )
    return None


def _is_precise_knowledge_reference(artifact: Any | None) -> bool:
    """Whether a KB reference identifies a bounded, citable source fragment."""
    if artifact is None:
        return False
    locator = getattr(artifact, "locator", None)
    if not isinstance(locator, dict):
        return False
    excerpt = getattr(artifact, "excerpt", None)
    if not isinstance(excerpt, str) or not excerpt.strip():
        return False
    chunk_id = locator.get("chunk_id")
    document_id = locator.get("document_id") or locator.get("doc_id")
    return bool(
        document_id is not None
        and str(document_id).strip()
        and isinstance(chunk_id, str)
        and chunk_id.strip()
        and getattr(artifact, "source_id", None) == chunk_id
        and getattr(artifact, "status", None) == "succeeded"
    )


def _validate_requested_knowledge_search(
    react_state: Dict[str, Any], artifacts: List[Any]
) -> str | None:
    """Do not finish a KB-requested report without an actual lookup attempt."""
    if not react_state.get("_report_knowledge_requested"):
        return None
    if not react_state.get("_report_knowledge_space"):
        return (
            "KNOWLEDGE_SPACE_REQUIRED: The user requested knowledge-base evidence, "
            "but no knowledge space is attached to this conversation. Ask the user "
            "to select the intended knowledge space before generating the report."
        )
    if any(
        getattr(artifact, "status", None) == "succeeded"
        and getattr(artifact, "type", None) == "reference"
        and getattr(artifact, "reference_type", None) == "knowledge"
        for artifact in artifacts
    ):
        return None
    if not react_state.get("_report_knowledge_search_attempted"):
        return (
            "KNOWLEDGE_SEARCH_REQUIRED: A knowledge space is attached, but no "
            "knowledge result was used or searched. Use kb_grep, semantic_search, "
            "or kb_cat to inspect the relevant metric rules, then retry the report. "
            "If no applicable rule is found, say so instead of inventing a KB citation."
        )
    return None


def _validate_requested_knowledge_bindings(html, react_state, references):
    """A lookup alone does not establish a report's use of the selected KB."""
    if not react_state.get("_report_knowledge_requested") or not references:
        return None
    requested = str(react_state.get("_report_knowledge_space") or "")
    candidates = {
        artifact_id: artifact
        for artifact_id, artifact in references.items()
        if requested
        in {
            str((artifact.locator or {}).get("knowledge_id") or ""),
            str((artifact.locator or {}).get("space_id") or ""),
        }
    }
    if not candidates:
        return None
    for match in iter_binding_tags(html):
        if match.group(0).split(None, 1)[0].lower() in {"<html", "<body", "<main"}:
            continue
        binding = parse_binding(match)
        if set(binding["artifact_ids"]).intersection(candidates):
            return None
    return (
        "KB_REPORT_BINDING_REQUIRED: The selected knowledge space was read, "
        "but no captured source slice is bound to report content. "
        "Use report_evidence_manifest(artifact_types=['reference'], detail=true) "
        "to inspect the relevant slices, then bind "
        "only the supporting reference artifact to the specific methodology "
        "statement or governed metric container. A lookup or whole-page binding "
        "does not establish this link. quote is optional; keep numeric values "
        "bound to their producing SQL/Python artifacts. For REPORT_SPEC, preserve "
        "the saved sections and add note={parts:[a methodology statement], "
        "ref:{artifact_id:the supporting captured reference ID, quote:optional exact "
        "source sentence}} to the relevant section. Read only selected reference "
        "IDs with artifact_ids + detail=true; a broad detail request over twelve "
        "artifacts returns a catalog. Reuse completed analysis."
    )


def _bind_generated_chart_images(html: str, artifacts: List[Any]) -> str:
    """Give each known generated image its own chart/Python lineage binding.

    This is deliberately limited to an image whose URL exactly identifies a
    captured ChartArtifact.  It neither assigns SQL evidence to unrelated
    content nor replaces the model's required KPI/claim bindings.
    """
    by_id = {getattr(artifact, "artifact_id", ""): artifact for artifact in artifacts}
    charts = {}
    for artifact in artifacts:
        if (
            getattr(artifact, "type", "") != "chart"
            or getattr(artifact, "status", "") != "succeeded"
        ):
            continue
        output = getattr(artifact, "output", None)
        uri = getattr(output, "uri", None) if output is not None else None
        if uri:
            charts.setdefault(str(uri).split("?", 1)[0], []).append(artifact)

    def lineage(artifact_id: str, seen: set[str] | None = None) -> List[str]:
        seen = seen or set()
        if artifact_id in seen:
            return []
        seen.add(artifact_id)
        artifact = by_id.get(artifact_id)
        if artifact is None:
            return []
        values: List[str] = []
        for input_id in getattr(artifact, "input_artifact_ids", []) or []:
            values.extend(lineage(input_id, seen))
        values.append(artifact_id)
        return values

    def annotate(match: re.Match) -> str:
        attrs = match.group("attrs")
        src = re.search(r"\bsrc\s*=\s*(['\"])(.*?)\1", attrs, re.IGNORECASE)
        if not src:
            return match.group(0)
        candidates = charts.get(unescape_html(src.group(2)).split("?", 1)[0], [])
        if len(candidates) != 1:
            return match.group(0)
        chart = candidates[0]
        ids = list(dict.fromkeys(lineage(chart.artifact_id)))
        existing = re.search(
            r"\bdata-dbgpt-artifacts\s*=\s*(['\"])([^'\"]+)\1",
            attrs,
            re.IGNORECASE,
        )
        if existing:
            merged = list(
                dict.fromkeys(
                    [
                        *(item.strip() for item in existing.group(2).split(",")),
                        *ids,
                    ]
                )
            )
            attrs = (
                attrs[: existing.start(2)] + ",".join(merged) + attrs[existing.end(2) :]
            )
        else:
            attrs += (
                f' data-dbgpt-artifacts="{",".join(ids)}"'
                ' data-dbgpt-evidence-label="生成图表"'
            )
        return f"<img{attrs}>"

    return re.sub(r"<img\b(?P<attrs>[^>]*)>", annotate, html, flags=re.IGNORECASE)


def _attach_native_charts_to_matching_tables(html: str, artifacts: List[Any]) -> str:
    """Give an executed native chart its own figure beside its source table.

    ``chart_query`` has already produced a concrete ``ChartArtifact``. A
    report author sometimes keeps the corresponding SQL table but drops the
    chart ID after being correctly told not to bind a chart to ``<table>``.
    That makes a successful chart disappear from the report. This adapter
    restores only that direct SQL -> chart relationship: it injects a separate
    empty figure immediately before the table, where the existing frontend
    mounts DB-GPT's native ``AutoChart``. It never creates a chart from SQL,
    and it never promotes exploratory charts whose source SQL is absent from
    the rendered report.
    """
    native_charts = [
        artifact
        for artifact in artifacts
        if getattr(artifact, "status", "") == "succeeded"
        and getattr(artifact, "type", "") == "chart"
        and getattr(getattr(artifact, "execution", None), "action", "")
        == "chart_action.render"
    ]
    if not native_charts:
        return html

    for chart in native_charts:
        chart_id = str(getattr(chart, "artifact_id", "")).strip()
        source_ids = [
            str(value).strip()
            for value in (getattr(chart, "input_artifact_ids", None) or [])
            if str(value).strip()
        ]
        if not chart_id or not source_ids:
            continue
        if any(
            match.group("tag").lower() == "figure"
            and chart_id in parse_binding(match)["artifact_ids"]
            for match in iter_binding_tags(html)
        ):
            continue

        table = next(
            (
                match
                for match in iter_binding_tags(html)
                if match.group("tag").lower() == "table"
                and set(source_ids).intersection(parse_binding(match)["artifact_ids"])
            ),
            None,
        )
        if table is None:
            continue
        label = escape_html(
            str(getattr(chart, "name", "") or "原生分析图表"), quote=True
        )
        ids = ",".join(dict.fromkeys([*source_ids, chart_id]))
        figure = (
            f'<figure data-dbgpt-artifacts="{ids}" '
            f'data-dbgpt-evidence-label="{label}" '
            'data-dbgpt-chart-placeholder="true"></figure>'
        )
        html = html[: table.start()] + figure + html[table.start() :]
    return html


def _normalize_concatenated_html_literals(html: str) -> str:
    """Compatibility entry for shared HTML serialization normalization."""
    if not isinstance(html, str) or not html:
        return html
    return normalize_report_html(html)


_NUMERIC_CLAIM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:[12]\d{3}[-/]\d{1,2}(?:[-/]\d{1,2})?|"
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?(?:\s*(?:亿元|万元|亿|万|元|[%％]|[kKmMbB]))?)(?![A-Za-z0-9_.-])"
)
_NUMERIC_CLAIM_SKIP_TAGS = {
    "head",
    "title",
    "script",
    "style",
    "code",
    "pre",
    "svg",
    "canvas",
}
_NON_METRIC_NUMBER_PREFIX = re.compile(
    r"(?<![A-Za-z0-9_])(?:图|表|figure|fig\.?|table|chart|top|第|章节|编号|序号|step)\s*[#№]?\s*$",
    re.IGNORECASE,
)
_ORDINAL_TITLE_PREFIX = re.compile(
    r"^\s*(?:图|表|figure|fig\.?|table|chart)\s*[#№]?\s*\d+",
    re.IGNORECASE,
)
_REDUNDANT_INLINE_EVIDENCE_ATTRS = (
    "data-dbgpt-artifacts",
    "data-dbgpt-evidence-label",
    "data-dbgpt-claim-id",
    "data-dbgpt-block-id",
)


def _strip_ordinal_title_bindings(html: str) -> str:
    """A figure/table number is a document label, not a measured value."""
    pattern = re.compile(
        r"<(?P<tag>h[1-6]|figcaption|caption|strong|b|span|em|mark)\b"
        r"(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
        re.IGNORECASE | re.DOTALL,
    )

    def strip(match: re.Match[str]) -> str:
        label = unescape_html(re.sub(r"<[^>]+>", "", match.group("body")))
        prefix = unescape_html(re.sub(r"<[^>]+>", "", html[: match.start()]))[-80:]
        split_ordinal = (
            match.group("tag").lower() in _INLINE_EVIDENCE_TAGS
            and re.fullmatch(r"\s*\d+\s*", label) is not None
            and _NON_METRIC_NUMBER_PREFIX.search(prefix) is not None
        )
        if not (_ORDINAL_TITLE_PREFIX.match(label) or split_ordinal):
            return match.group(0)
        value = match.group(0)
        for attribute in (*_REDUNDANT_INLINE_EVIDENCE_ATTRS, "data-dbgpt-target-kind"):
            value = re.sub(
                rf"\s+{re.escape(attribute)}\s*=\s*(['\"])[^'\"]*\1",
                "",
                value,
                flags=re.IGNORECASE,
            )
        return value

    # Process inline labels before outer headings, since a regex match on the
    # heading would otherwise consume and hide its nested bound number.
    inline_pattern = re.compile(
        r"<(?P<tag>strong|b|span|em|mark)\b"
        r"(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    html = inline_pattern.sub(strip, html)
    return pattern.sub(strip, html)


def _result_number(text: str) -> Tuple[Decimal, Decimal] | None:
    """Normalize recorded amounts/ratios and their displayed rounding interval."""
    match = re.fullmatch(
        r"([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?)(?:\s*(亿元|万元|亿|万|元|[%％]|[kKmMbB]))?",
        text.strip(),
    )
    if not match:
        return None
    number, unit = match.groups()
    scale = {
        "亿元": Decimal("1e8"),
        "亿": Decimal("1e8"),
        "万元": Decimal("1e4"),
        "万": Decimal("1e4"),
        "k": Decimal("1e3"),
        "K": Decimal("1e3"),
        "m": Decimal("1e6"),
        "M": Decimal("1e6"),
        "b": Decimal("1e9"),
        "B": Decimal("1e9"),
        "%": Decimal("0.01"),
        "％": Decimal("0.01"),
    }.get(unit, Decimal(1))
    try:
        value = Decimal(number.replace(",", "")) * scale
        mantissa, _, exponent = number.lower().partition("e")
        places = len(mantissa.partition(".")[2])
        tolerance = (
            Decimal("0.5") * Decimal(10) ** (int(exponent or 0) - places) * scale
        )
        return (value, tolerance) if value.is_finite() else None
    except InvalidOperation:
        return None


def _numeric_values(result: Any) -> set[Decimal]:
    """Extract scalar values without treating booleans or metadata as metrics."""
    values: set[Decimal] = set()

    def visit(value: Any, depth: int = 0) -> None:
        if depth > 32 or isinstance(value, bool):
            return
        if isinstance(value, (int, float, Decimal, str)):
            parsed = _result_number(str(value))
            if parsed:
                values.add(parsed[0])
            elif isinstance(value, str) and value.lstrip().startswith(("{", "[")):
                try:
                    visit(json.loads(value), depth + 1)
                except (ValueError, TypeError):
                    pass
        elif isinstance(value, dict):
            for item in value.values():
                visit(item, depth + 1)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item, depth + 1)

    visit(result)
    return values


def _artifact_numeric_values(artifact: Any) -> set[Decimal]:
    """Read captured result values, including rows omitted from the preview."""
    if getattr(artifact, "result", None) is None:
        return set()
    result = read_artifact_result(artifact)
    if (
        getattr(artifact, "type", None) == "sql"
        and isinstance(result, dict)
        and "rows" in result
    ):
        result = result["rows"]
    return _numeric_values(result)


def _chart_evidence_validator(artifacts):
    by_id = {
        item.artifact_id: item
        for item in artifacts
        if item.status == "succeeded" and item.type == "chart"
    }

    def supports(attributes, binding):
        if attributes["tag"] != "img":
            return True
        uri = (attributes.get("src") or "").split("?", 1)[0]
        return any(
            item in by_id
            and by_id[item].output is not None
            and by_id[item].output.uri
            and by_id[item].output.uri.split("?", 1)[0] == uri
            for item in binding["artifact_ids"]
        )

    return supports


def _numeric_evidence_validator(artifacts):
    """Share captured scalar matching with automatic binding; cache each selection."""
    by_id = {
        artifact.artifact_id: artifact
        for artifact in artifacts
        if artifact.status == "succeeded"
    }
    values = {}
    selected_text = {}

    def supports(number, binding, text):
        for artifact_id in binding["artifact_ids"]:
            artifact = by_id.get(artifact_id)
            if artifact is None or artifact.type not in {"sql", "python", "reference"}:
                continue
            selector = binding["artifact_selectors"].get(artifact_id, {})
            key = (artifact_id, json.dumps(selector, sort_keys=True))
            if key not in values:
                if artifact.type == "reference" or selector.get("kind") == "sql":
                    excerpt = (
                        selector.get("quote") or getattr(artifact, "excerpt", "") or ""
                    )
                    values[key] = {
                        parsed[0]
                        for match in _NUMERIC_CLAIM_PATTERN.finditer(excerpt)
                        if (parsed := _result_number(match[0]))
                    }
                elif "field" in selector or "path" in selector:
                    try:
                        selected = select_artifact_result(artifact, selector)
                        values[key] = _numeric_values(selected)
                        if isinstance(selected, str):
                            selected_text[key] = selected.strip()
                    except (ValueError, TypeError, OSError):
                        # The selector validator supplies the precise JSON path error.
                        return True
                else:
                    values[key] = _artifact_numeric_values(artifact)
            # Captured category labels may contain digits without being metrics.
            # Only the exact selected scalar text establishes that provenance.
            if key in selected_text and text.strip() == selected_text[key]:
                return True
            if selector.get("kind") == "sql":
                parsed = _result_number(number)
                if parsed and parsed[0] in values[key]:
                    return True
                continue
            if _matches_result_value(
                number, values[key], percent_scale=selector.get("kind") != "sql"
            ):
                return True
        return False

    return supports


def _matches_result_value(
    text: str, values: set[Decimal], *, percent_scale: bool = False
) -> bool:
    parsed = _result_number(text)
    if parsed is None:
        return False
    target, tolerance = parsed
    return any(
        abs(value - target) <= tolerance
        or (
            percent_scale
            and text.endswith(("%", "％"))
            and abs(value / 100 - target) <= tolerance
        )
        for value in values
    )


def _result_span(
    value: str, artifact_id: str, field: str | None = None, *, source_selector=None
) -> str:
    source_selector = source_selector or (
        {"kind": "result", "field": field} if field else None
    )
    selector = (
        " data-dbgpt-artifact-selectors='"
        + escape_html(
            json.dumps({artifact_id: source_selector}, ensure_ascii=False),
            quote=True,
        )
        + "'"
        if source_selector
        else ""
    )
    return (
        f'<span data-dbgpt-artifacts="{artifact_id}"{selector} '
        f'data-dbgpt-evidence-label="{escape_html(value, quote=True)}">'
        f"{value}</span>"
    )


def _template_result_sources(artifacts: List[Any]) -> Dict[str, Any]:
    """Resolve placeholder fields directly from captured results, in run order."""
    sources = {}
    for artifact in artifacts:
        result = getattr(getattr(artifact, "result", None), "inline", None)
        if getattr(artifact, "status", None) != "succeeded" or not isinstance(
            result, dict
        ):
            continue
        for field, value in result.items():
            if (
                isinstance(field, str)
                and field.isupper()
                and isinstance(value, (str, int, float, dict, list))
                and not isinstance(value, bool)
            ):
                sources[field] = {
                    "artifact_id": artifact.artifact_id,
                    "field": field,
                    "value": value,
                }
    return sources


# Data keys that turn a mapping into an evidence reference instead of a literal.
_TEMPLATE_REFERENCE_KEYS = {
    "artifact_id",
    "field",
    "path",
    "kind",
    "quote",
    "format",
    "suffix",
    "proposal",
}
# A table may name its producer and columns; the engine expands the cells.
_TABLE_NODE_KEYS = {
    "artifact_id",
    "field",
    "path",
    "columns",
    "rows",
    "limit",
    "offset",
    "label",
}
_TABLE_COLUMN_KEYS = {"field", "label", "format"}


def _format_reference_value(value: Any, fmt: str | None) -> str:
    """Render a captured value the way the report displays it."""
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str) or fmt in {"text", "raw"}:
        return str(value)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if not number.is_finite():
        return str(value)
    if fmt in {"pct", "percent", "pct1", "pct2", "pct0"}:
        return f"{number:.{1 if fmt == 'pct1' else 0 if fmt == 'pct0' else 2}f}%"
    if fmt in {"int", "num0"}:
        return f"{number:,.0f}"
    if fmt == "num1":
        return f"{number:,.1f}"
    if fmt in {"money", "money2", "num2"}:
        return f"{number:,.2f}"
    # Keep whole numbers exact and round decimals to the displayed precision.
    if number == number.to_integral_value():
        return f"{number:,.0f}"
    return f"{number:,.2f}"


def _available_result_hint(artifact: Any) -> str:
    """Name the result keys a rejected selector could have used."""
    try:
        result = read_artifact_result(artifact)
    except (ValueError, TypeError, OSError):
        return "No captured result is available for this artifact."
    if isinstance(result, dict):
        hint = f"Available result keys: {list(result)[:12]}."
        rows = result.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            hint += f" Row keys: {list(rows[0])[:12]}."
        return hint + " "
    if isinstance(result, list):
        return f"Result is a row list with {len(result)} entries. "
    return ""


def _resolve_reference_node(
    node: Dict[str, Any], by_id: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve one ``{artifact_id, field/path}`` node into bound display text."""
    artifact_id = str(node["artifact_id"])
    artifact = by_id.get(artifact_id)
    if artifact is None:
        raise ValueError(
            "REPORT_TEMPLATE_REFERENCE_INVALID: attribute=data; "
            f"unknown or unsuccessful artifact {artifact_id}"
        )
    if getattr(artifact, "type", None) == "chart":
        chart = {"refs": [artifact_id], "caption": getattr(artifact, "name", "图表")}
        uri = getattr(getattr(artifact, "output", None), "uri", None)
        if uri:
            chart["img"] = uri
        else:
            if (
                getattr(getattr(artifact, "execution", None), "action", "")
                != "chart_action.render"
            ):
                chart["renderer"] = "echarts"
        raise ValueError(
            "REPORT_TEMPLATE_REFERENCE_INVALID: attribute=data; "
            f"artifact={artifact_id}; type=chart has an output, not a numeric result. "
            "Move it to sections[].chart using "
            + json.dumps(chart, ensure_ascii=False)
            + ". Use the producing SQL/Python artifact for numeric values."
        )
    selector = {
        key: node[key] for key in ("field", "path", "kind", "quote") if key in node
    }
    if getattr(artifact, "type", None) == "reference":
        # A captured source slice has no numeric result; its evidence is the
        # captured excerpt plus an optional quote from that excerpt.
        excerpt = getattr(artifact, "excerpt", None) or ""
        if not excerpt.strip():
            raise ValueError(
                "REPORT_TEMPLATE_REFERENCE_INVALID: attribute=data; "
                f"artifact={artifact_id}; the captured source has no excerpt text"
            )
        quote = selector.get("quote")
        if isinstance(quote, str) and quote.strip():
            if " ".join(quote.split()) not in " ".join(excerpt.split()):
                raise ValueError(
                    "REPORT_TEMPLATE_REFERENCE_INVALID: attribute=data; "
                    f"artifact={artifact_id}; "
                    f"selector={json.dumps(selector, ensure_ascii=False)}; quote "
                    "must be text from this captured excerpt"
                )
        text = quote if isinstance(quote, str) and quote.strip() else excerpt
        proposal = node.get("proposal")
        if proposal:
            selector.setdefault("quote", excerpt)
            text = f"建议目标（非观测值）：{proposal}"
        if node.get("suffix"):
            text = f"{text}{node['suffix']}"
        return {
            "value": text,
            "raw": excerpt,
            "artifact_id": artifact_id,
            "selector": selector or None,
            "selectors": {artifact_id: selector} if selector else None,
            "proposal": bool(proposal),
        }
    try:
        selector = normalize_artifact_result_selector(artifact, selector)
        raw = (
            select_artifact_result(artifact, selector)
            if selector
            else read_artifact_result(artifact)
        )
    except (ValueError, TypeError, OSError) as error:
        try:
            context = "Selector context: " + json.dumps(
                result_selector_context(artifact, selector), ensure_ascii=False
            )
        except (ValueError, TypeError, OSError):
            context = ""
        raise ValueError(
            "REPORT_TEMPLATE_REFERENCE_INVALID: attribute=data; "
            f"artifact={artifact_id}; "
            f"selector={json.dumps(selector, ensure_ascii=False)}; {error}. "
            + _available_result_hint(artifact)
            + context
        ) from error
    text = _format_reference_value(raw, node.get("format"))
    if node.get("proposal"):
        if not ("field" in selector or "path" in selector):
            raise ValueError(
                (
                    "REPORT_TEMPLATE_REFERENCE_INVALID: a proposal needs a selected "
                    "SQL/Python result supporting its "
                    "rationale"
                )
            )
        text = f"建议目标（非观测值）：{node['proposal']}"
    if node.get("suffix"):
        text = f"{text}{node['suffix']}"
    return {
        "value": text,
        "raw": raw,
        "artifact_id": artifact_id,
        "selector": selector or None,
        "selectors": {artifact_id: selector} if selector else None,
        "proposal": bool(node.get("proposal")),
    }


def _table_columns(columns: Any) -> List[Dict[str, Any]]:
    """Normalize a table's column list into field/label/format triples."""
    normalized = []
    for column in columns or []:
        if isinstance(column, str) and column.strip():
            normalized.append({"field": column, "label": column, "format": None})
        elif isinstance(column, dict) and isinstance(column.get("field"), str):
            unknown = set(column) - _TABLE_COLUMN_KEYS
            if unknown:
                raise ValueError(
                    "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; "
                    f"unknown column keys: {sorted(unknown)}"
                )
            normalized.append(
                {
                    "field": column["field"],
                    "label": column.get("label") or column["field"],
                    "format": column.get("format"),
                }
            )
        else:
            raise ValueError(
                "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; each column must be "
                'a field name or {"field","label","format"}'
            )
    if not normalized:
        raise ValueError(
            "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; table needs columns"
        )
    return normalized


def _expand_table(node: Dict[str, Any], by_id: Dict[str, Any]) -> Dict[str, Any]:
    """Build a table body from the artifact's own rows.

    One reference node per cell costs about a hundred characters, which
    overruns a report's output budget on any real table. Naming the producer
    and the columns lets the engine expand every cell with its own selector.
    """
    artifact_id = str(node["artifact_id"])
    artifact = by_id.get(artifact_id)
    if artifact is None:
        raise ValueError(
            "REPORT_TEMPLATE_REFERENCE_INVALID: attribute=data; "
            f"unknown or unsuccessful artifact {artifact_id}"
        )
    selector = {key: node[key] for key in ("field", "path") if key in node}
    try:
        result = (
            select_artifact_result(artifact, selector)
            if selector
            else read_artifact_result(artifact)
        )
        if isinstance(result, str):
            result = json.loads(result)
    except (ValueError, TypeError, OSError) as error:
        raise ValueError(
            "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; "
            f"artifact={artifact_id}; {error}"
        ) from error
    if isinstance(result, dict) and isinstance(result.get("rows"), list):
        source = result["rows"]
        row_path = [*(selector.get("path") or []), "rows"]
        header = result.get("columns", result.get("headers", []))
        if not isinstance(header, list):
            header = []
    elif isinstance(result, list):
        source, header = result, []
        row_path = list(selector.get("path") or [])
        if row_path and row_path[-1] == "rows":
            parent = select_artifact_result(
                artifact, {**selector, "path": row_path[:-1]}
            )
            if isinstance(parent, str):
                parent = json.loads(parent)
            if isinstance(parent, dict):
                header = parent.get("columns", parent.get("headers", []))
                if not isinstance(header, list):
                    header = []
    else:
        raise ValueError(
            "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; "
            f"artifact={artifact_id} has no row result"
        )
    offset = node.get("offset") or 0
    limit = node.get("limit")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError(
            "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; offset must be a "
            "nonnegative integer"
        )
    if limit is not None and (
        not isinstance(limit, int) or isinstance(limit, bool) or limit < 0
    ):
        raise ValueError(
            "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; limit must be a "
            "nonnegative integer"
        )
    window = source[offset:] if limit is None else source[offset : offset + limit]
    columns = _table_columns(node["columns"])
    rows = []
    for position, row in enumerate(window):
        index = offset + position
        cells = []
        for column in columns:
            field = column["field"]
            if isinstance(row, dict):
                key: Any = field if field in row else None
            else:
                key = header.index(field) if field in header else None
            if key is None:
                raise ValueError(
                    "REPORT_TEMPLATE_TABLE_INVALID: attribute=data; "
                    f"artifact={artifact_id}; column {field!r} is not in the result"
                )
            cells.append(
                _resolve_reference_node(
                    {
                        "artifact_id": artifact_id,
                        **({"field": selector["field"]} if "field" in selector else {}),
                        "path": [*row_path, index, key],
                        **({"format": column["format"]} if column["format"] else {}),
                    },
                    by_id,
                )
            )
        rows.append(cells)
    return {
        "artifact_id": artifact_id,
        "label": node.get("label"),
        "columns": [column["label"] for column in columns],
        "rows": rows,
    }


def _resolve_template_references(
    data: Any,
    artifacts: List[Any],
    *,
    errors: list | None = None,
    unavailable_references: list | None = None,
) -> Any:
    """Resolve ``{artifact_id, field/path}`` data nodes into bound display text.

    A template renders the value the engine resolved from a captured artifact,
    so the model cannot invent a report number: it can only point at a real
    result field, and a wrong pointer fails here instead of being saved. A
    table may name its producer and columns instead of listing every cell.
    """
    by_id = {
        artifact.artifact_id: artifact
        for artifact in artifacts
        if getattr(artifact, "status", "") == "succeeded"
    }

    issues = errors if errors is not None else []

    def resolve(node: Any, path: str = "$.data") -> Any:
        if isinstance(node, list):
            return [
                resolve(item, f"{path}[{index}]") for index, item in enumerate(node)
            ]
        if not isinstance(node, dict):
            return node
        try:
            if node.get("artifact_id") and set(node).issubset(_TEMPLATE_REFERENCE_KEYS):
                if node.get("proposal") and ".recommendations[" not in path:
                    raise ValueError(
                        (
                            "REPORT_TEMPLATE_REFERENCE_INVALID: proposal is "
                            "allowed only in "
                            "recommendation lines, never KPI or observed-value "
                            "targets"
                        )
                    )
                return _resolve_reference_node(node, by_id)
            if (
                node.get("artifact_id")
                and "columns" in node
                and "rows" not in node
                and set(node).issubset(_TABLE_NODE_KEYS)
            ):
                return _expand_table(node, by_id)
            if path.endswith(".chart") and isinstance(node.get("refs"), list):
                node = dict(node)
                refs = node["refs"]
                missing = [item for item in refs if item not in by_id]
                if missing:
                    raise ValueError(
                        (
                            "REPORT_TEMPLATE_CHART_INVALID: unknown chart references "
                            f"{missing}"
                        )
                    )
                charts = [by_id[item] for item in refs if by_id[item].type == "chart"]
                prepared = [
                    chart
                    for chart in charts
                    if chart.spec.get("renderer") == "echarts"
                    and isinstance(chart.spec.get("option"), dict)
                ]
                if len(prepared) == 1:
                    chart = prepared[0]
                    source_id = chart.spec["source_artifact_id"]
                    node.update(
                        renderer="echarts",
                        chart_id=chart.artifact_id,
                        option=chart.spec["option"],
                        height=chart.spec["height"],
                        maps=chart.spec.get("maps", {}),
                        source_selectors=chart.spec.get("source_selectors"),
                        producer={
                            "artifact_id": source_id,
                            **chart.spec["source_selector"],
                        },
                    )
                    node["refs"] = list(dict.fromkeys([*refs, source_id]))
                    refs = node["refs"]
                if node.get("renderer") == "echarts":
                    node.setdefault(
                        "host_id",
                        "report-chart-"
                        + hashlib.sha256(path.encode()).hexdigest()[:12],
                    )
                    if not node.get("producer"):
                        raise ValueError(
                            (
                                "REPORT_TEMPLATE_CHART_INVALID: an ECharts host "
                                "requires a "
                                "producing SQL/Python reference in "
                                "producer"
                            )
                        )
                    if (
                        node.get("producer")
                        and node["producer"].get("artifact_id") not in refs
                    ):
                        raise ValueError(
                            (
                                "REPORT_TEMPLATE_CHART_INVALID: "
                                "producer.artifact_id must be in "
                                "refs"
                            )
                        )
                    try:
                        _resolve_reference_node(node["producer"], by_id)
                    except (ValueError, TypeError, OSError) as error:
                        raise ValueError(
                            "REPORT_TEMPLATE_CHART_INVALID: invalid ECharts producer; "
                            + str(error)
                        ) from error
                else:
                    images = [
                        chart
                        for chart in charts
                        if getattr(getattr(chart, "output", None), "uri", None)
                    ]
                    native = [
                        chart
                        for chart in charts
                        if chart.execution.action == "chart_action.render"
                    ]
                    if len(native) == 1 and not node.get("img"):
                        # The existing report frontend mounts DB-GPT AutoChart
                        # inside this figure, using the captured native spec.
                        pass
                    elif len(images) != 1:
                        raise ValueError(
                            (
                                "REPORT_TEMPLATE_CHART_INVALID: image chart "
                                "requires exactly one "
                                "captured ChartArtifact with "
                                "output.uri"
                            )
                        )
                    else:
                        uri = images[0].output.uri
                        if node.get("img") and node["img"] != uri:
                            raise ValueError(
                                (
                                    "REPORT_TEMPLATE_CHART_INVALID: img must "
                                    "match captured "
                                    "output.uri="
                                    f"{uri}"
                                )
                            )
                        node["img"] = uri
            return {key: resolve(value, f"{path}.{key}") for key, value in node.items()}
        except (ValueError, TypeError, OSError) as error:
            if (
                unavailable_references is not None
                and node.get("artifact_id") in by_id
                and by_id[node["artifact_id"]].type == "reference"
                and set(node).issubset(_TEMPLATE_REFERENCE_KEYS)
                and "quote must be text from this captured excerpt" in str(error)
            ):
                # quote is optional. Preserve the selected slice and actual text,
                # never an invented quotation or a different supporting source.
                unavailable_references.append(
                    {"json_path": path, "citation": node, "error": str(error)}
                )
                return _resolve_reference_node(
                    {key: value for key, value in node.items() if key != "quote"}, by_id
                )
            if (
                unavailable_references is not None
                and path.endswith(".chart")
                and "REPORT_TEMPLATE_CHART_INVALID" in str(error)
            ):
                # A missing optional visualization does not invalidate the
                # independently bound analysis, table or methodology in its section.
                unavailable_references.append(
                    {"json_path": path, "chart": node, "error": str(error)}
                )
                return None
            if (
                unavailable_references is not None
                and node.get("artifact_id") in by_id
                and set(node).issubset(_TEMPLATE_REFERENCE_KEYS)
                and "RESULT_SELECTOR_INVALID" in str(error)
            ):
                # Missing display values must never be guessed or rebound to an
                # unrelated number just to make the rest of a report deliverable.
                unavailable_references.append(
                    {"json_path": path, "reference": node, "error": str(error)}
                )
                return "--"
            issues.append({"json_path": path, "error": str(error)})
            return node

    resolved = resolve(data)
    if issues and errors is None:
        raise ValueError(
            "REPORT_TEMPLATE_REFERENCE_INVALID: "
            + json.dumps(issues, ensure_ascii=False)
        )
    return resolved


def _saved_report_spec(state: Dict[str, Any]) -> Any:
    """Read the REPORT_SPEC kept in the last accepted template arguments."""
    saved = state.get("_report_saved_arguments")
    if not isinstance(saved, dict):
        return None
    data = saved.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            return None
    if isinstance(data, dict):
        spec = data.get("REPORT_SPEC")
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except ValueError:
                return None
        return spec if isinstance(spec, dict) else None
    return None


def _merge_report_spec(
    replacements: Dict[str, Any], state: Dict[str, Any]
) -> Dict[str, Any]:
    """Append a piecewise spec to the saved one.

    A whole report does not always fit in one model output. ``sections`` and
    ``kpis`` of ``REPORT_SPEC_APPEND`` are appended to the saved spec and every
    other key overwrites it, so a long report can be built across calls without
    resending what was already accepted.
    """
    addition = replacements.pop("REPORT_SPEC_APPEND", None)
    if addition is not None and not isinstance(addition, dict):
        raise ValueError(
            "REPORT_TEMPLATE_SPEC_INVALID: attribute=data; "
            "$.data.REPORT_SPEC_APPEND must be an object with sections/kpis."
        )
    if not isinstance(addition, dict):
        return replacements
    base = replacements.get("REPORT_SPEC")
    if isinstance(base, str):
        try:
            base = json.loads(base)
        except ValueError as error:
            raise ValueError(
                "REPORT_TEMPLATE_SPEC_INVALID: attribute=data; "
                "$.data.REPORT_SPEC must contain valid JSON before appending."
            ) from error
    if not isinstance(base, dict):
        base = _saved_report_spec(state)
    merged = dict(base or {})
    for key, value in addition.items():
        if key in {"sections", "kpis"} and isinstance(value, list):
            items = list(merged.get(key) or [])
            for item in value:
                if item not in items:
                    items.append(item)
            merged[key] = items
        else:
            merged[key] = value
    replacements["REPORT_SPEC"] = merged
    saved = state.get("_report_saved_arguments")
    if isinstance(saved, dict):
        data = saved.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                data = None
        if isinstance(data, dict):
            # Keep the merged spec so the next render does not append it twice.
            saved["data"] = {
                key: value for key, value in data.items() if key != "REPORT_SPEC_APPEND"
            }
            saved["data"]["REPORT_SPEC"] = merged
    return replacements


_PROSE_KEYS = ("intro", "bullets", "list")


def _spec_strings(value: Any):
    """Yield the model-authored body strings of a spec fragment."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _spec_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _spec_strings(item)


def _has_evidence(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("artifact_id"):
            return True
        if isinstance(value.get("refs"), list) and value["refs"]:
            # Chart references are checked against real captured IDs after rendering.
            return True
        if value.get("document_id") or value.get("doc_id") or value.get("chunk_id"):
            # A knowledge locator cites the captured document chunk.
            return True
        return any(_has_evidence(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_evidence(item) for item in value)
    return False


def _spec_evidence_error(spec: Any, artifacts: List[Any]) -> str | None:
    """Name every unbound literal value, even beside correctly referenced values."""
    if not isinstance(spec, dict):
        return None
    sections = spec.get("sections")
    if not isinstance(sections, list):
        return None

    def strings(value, path):
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from strings(child, f"{path}[{index}]")
        elif isinstance(value, dict) and not value.get("artifact_id"):
            for key, child in value.items():
                yield from strings(child, f"{path}.{key}")

    targets = []

    def kpi_text(items):
        return [
            {key: item[key] for key in ("label", "unit", "hint") if key in item}
            for item in items
            if isinstance(item, dict)
        ]

    root_text = {
        key: spec[key] for key in ("title", "subtitle", "scope") if key in spec
    }
    root_text["kpis"] = kpi_text(spec.get("kpis", []))
    authored_text = [("$.data.REPORT_SPEC", "报告信息", root_text)]
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        base = f"$.data.REPORT_SPEC.sections[{index}]"
        prose = {key: section[key] for key in _PROSE_KEYS if key in section}
        prose.update({key: section[key] for key in ("heading",) if key in section})
        prose["kpis"] = kpi_text(section.get("kpis", []))
        if isinstance(section.get("chart"), dict):
            prose["chart"] = {"caption": section["chart"].get("caption", "")}
        if isinstance(section.get("note"), dict):
            prose["note"] = {"parts": section["note"].get("parts", [])}
        if isinstance(section.get("table"), dict) and "rows" in section["table"]:
            prose["table"] = {"rows": section["table"]["rows"]}
        if section.get("recommendations"):
            prose["recommendations"] = [
                {
                    **{
                        key: recommendation[key]
                        for key in ("title", "badge")
                        if key in recommendation
                    },
                    "lines": [
                        {"parts": line.get("parts", [])}
                        if isinstance(line, dict)
                        else {}
                        for line in recommendation.get("lines") or []
                    ],
                }
                if isinstance(recommendation, dict)
                else {}
                for recommendation in section["recommendations"]
            ]
        authored_text.append((base, section.get("heading") or f"#{index + 1}", prose))
    for base, container, prose in authored_text:
        for path, text in strings(prose, base):
            values = [
                match[0]
                for match in _NUMERIC_CLAIM_PATTERN.finditer(text)
                if not is_document_number(
                    match[0],
                    text[match.end() :],
                    text[: match.start()],
                    _NON_METRIC_NUMBER_PREFIX,
                )
            ]
            if values:
                targets.append(
                    {
                        "json_path": path,
                        "container": container,
                        "values": values,
                        "text": text,
                    }
                )
    if targets:
        return (
            "REPORT_TEMPLATE_SPEC_INVALID: "
            + json.dumps(targets, ensure_ascii=False)
            + ". attribute=data; replace every listed literal number with its "
            "own reference node; preserve the prose around it. A nearby KPI or "
            "section binding does not bind these values. Or use a producer table "
            "and summarize it without literal numbers. Repair all targets together. "
            "Result producers (not KB-only IDs): "
            + json.dumps(result_evidence_catalog(artifacts), ensure_ascii=False)
            + ". Choose sources by metric meaning; equal numbers alone do not "
            "prove a source. Read selected IDs with report_evidence_manifest "
            "artifact_ids + detail=true. An uncaptured derived total is not an "
            "observed result: capture that calculation in analysis or omit its "
            "number. Reuse the saved spec and completed artifacts."
        )
    kpis = spec.get("kpis")
    items = [
        item
        for item in list(sections) + (kpis if isinstance(kpis, list) else [])
        if isinstance(item, dict)
    ]
    if items and not any(_has_evidence(item) for item in items):
        has_digit = any(
            re.search(r"\d", text) for item in items for text in _spec_strings(item)
        )
        if has_digit:
            # Values carrying digits (a literal or an unknown reference) get named by
            # the binding checks; do not shadow them with this generic message.
            return None
        return (
            "REPORT_TEMPLATE_SPEC_INVALID: attribute=data; REPORT_SPEC cites no "
            "captured artifact. Bind at least one KPI, table, chart or value to a real "
            'artifact id ({"artifact_id": ..., "field"/"path": ...}). Available '
            "artifacts: "
            + ", ".join(str(getattr(item, "artifact_id", "")) for item in artifacts[:6])
            + "."
        )
    return None


def report_template_contract(template: str) -> dict:
    """Derive the input contract from the selected template, not its skill name."""
    uses_spec = bool(
        re.search(
            r"template_data(?:\.REPORT_SPEC\b|\s*\[\s*['\"]REPORT_SPEC['\"]|"
            r"\.get\(\s*['\"]REPORT_SPEC['\"])|\{\{\s*REPORT_SPEC\s*\}\}",
            template,
        )
    )
    fields = sorted(set(re.findall(r"\{\{([A-Z_0-9]+)\}\}", template)))
    prose_fields = sorted(
        set(
            re.findall(
                r"<[\w:-]+\b[^>]*\bclass\s*=\s*['\"][^'\"]*\bprose\b[^'\"]*['\"][^>]*>"
                r"\s*\{\{([A-Z_0-9]+)\}\}",
                template,
            )
        )
    )
    return {
        "mode": "spec" if uses_spec else "placeholders",
        "fields": fields,
        "prose_fields": prose_fields,
    }


def _render_placeholder_parts(value: Any) -> str:
    """Render structured prose as paragraphs, keeping each value's source."""
    if isinstance(value, dict) and value.get("artifact_id") and "value" in value:
        return _result_span(
            escape_html(str(value["value"])),
            value["artifact_id"],
            source_selector=value.get("selector"),
        )
    if isinstance(value, dict):
        tag = value.get("type")
        refs = value.get("refs", [])
        if (
            set(value).issubset({"type", "text", "refs"})
            and isinstance(value.get("text"), str)
            and tag in {None, "p", "li", "span"}
            and isinstance(refs, list)
            and all(
                isinstance(ref, dict) and ref.get("artifact_id") and "value" in ref
                for ref in refs
            )
        ):
            content = validate_template_fragment(value["text"]) + "".join(
                _render_placeholder_parts(ref) for ref in refs
            )
            return f"<{tag}>{content}</{tag}>" if tag else content
        # A Python repr is never a valid fallback for authored report objects.
        # Reject unknown shapes so the repair loop can correct the input.
        raise ValueError(
            "REPORT_TEMPLATE_PROSE_INVALID: use strings, lists of inline parts, "
            "or {type: p/li/span, text: string, refs: [artifact_id/field/path nodes]}; "
            "unsupported prose fields: " + ", ".join(sorted(map(str, value)))
        )
    if isinstance(value, list):
        return "".join(
            "<p>" + "".join(_render_placeholder_parts(part) for part in item) + "</p>"
            if isinstance(item, list)
            else _render_placeholder_parts(item)
            for item in value
        )
    # Authored HTML fragments follow the existing string-placeholder contract.
    # Captured reference values remain escaped above.
    return validate_template_fragment(str(value))


def _resolve_inline_report_references(html: str, artifacts: List[Any]) -> str:
    """Resolve references emitted as prose instead of structured template nodes.

    Only visible text is interpreted. Attributes, scripts and code examples retain
    their contents, and every recovered reference uses the ordinary selector
    validation rather than guessing a value from the displayed analysis.
    """
    by_id = {
        item.artifact_id: item
        for item in artifacts
        if getattr(item, "status", "") == "succeeded"
    }
    quote = r"(?:[\"']|&quot;|&apos;|&#0*39;|&#x0*27;)"
    start = re.compile(r"\{\s*" + quote + r"?artifact_id" + quote + r"?\s*:", re.I)
    reference = re.compile(start.pattern + r"[^{}]*\}", start.flags)
    stack = []
    output = []

    def replace(match):
        raw = unescape_html(match[0])
        try:
            node = json.loads(raw)
        except ValueError:
            try:
                # Python-style dictionaries also appear in model-written prose.
                # literal_eval accepts quoted paths without executing expressions.
                node = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                node = None
        if node is None:
            # Models also emit compact, unquoted references in HTML prose.
            # Accept only flat key/value pairs; complex values must be quoted.
            node = {}
            for pair in raw[1:-1].split(","):
                key, separator, value = pair.partition(":")
                key, value = key.strip(), value.strip()
                if not separator or not value or key in node:
                    raise ValueError(
                        "REPORT_TEMPLATE_REFERENCE_INVALID: "
                        "malformed inline reference; "
                        "use a structured artifact_id and field/path node"
                    )
                node[key] = value
            if "path" in node:
                node["path"] = re.sub(r"\.(\d+)(?=\.|$)", r"[\1]", node["path"])
        if not isinstance(node, dict) or not set(node).issubset(
            _TEMPLATE_REFERENCE_KEYS
        ):
            raise ValueError(
                "REPORT_TEMPLATE_REFERENCE_INVALID: unsupported inline reference fields"
            )
        return _render_placeholder_parts(_resolve_reference_node(node, by_id))

    for token in html_tokens(html):
        opening = re.match(r"<\s*([\w:-]+)\b", token)
        closing = re.match(r"</\s*([\w:-]+)", token)
        if closing:
            tag = closing[1].lower()
            if tag in stack:
                del stack[len(stack) - 1 - stack[::-1].index(tag) :]
        elif opening:
            tag = opening[1].lower()
            if tag in {"script", "style", "pre", "code"}:
                stack.append(tag)
        elif not stack:
            if start.search(reference.sub("", token)):
                raise ValueError(
                    "REPORT_TEMPLATE_REFERENCE_INVALID: incomplete inline reference"
                )
            token = reference.sub(replace, token)
        output.append(token)
    return "".join(output)


def _render_template_with_bindings(
    template: str,
    data: Dict[str, Any],
    artifacts: List[Any],
    *,
    required_recommendations: int | None = None,
    draft_state: Dict[str, Any] | None = None,
    allow_unavailable_references: bool = False,
) -> str:
    """Use the existing placeholders, retaining a numeric field's producer."""
    data = dict(data)
    contract = report_template_contract(template)
    if contract["mode"] == "placeholders" and "REPORT_SPEC" in data:
        payload = data["REPORT_SPEC"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict) and not set(payload).intersection(
            {"title", "subtitle", "scope", "sections", "kpis"}
        ):
            # Legacy templates consume named fields. Models sometimes wrap those
            # fields in REPORT_SPEC; preserve their values without applying an
            # unrelated business-spec schema or silently discarding the content.
            data.pop("REPORT_SPEC")
            data = {**payload, **data}
    if "REPORT_SPEC" in data:
        spec = data["REPORT_SPEC"]
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "REPORT_TEMPLATE_SPEC_INVALID: attribute=data; "
                    f"$.data.REPORT_SPEC JSON line {error.lineno}, column "
                    f"{error.colno}, position {error.pos}: {error.msg}"
                ) from error
        data["REPORT_SPEC"] = _normalize_report_chart_nodes(spec, artifacts)
    errors = []
    extra_charts = data.pop("REPORT_CHARTS", None)
    if extra_charts is not None:
        try:
            from .report_chart_options import prepare_option_charts

            extra_spec = validate_report_spec(
                {"sections": [{"chart": node} for node in extra_charts]}
            )
            sink = (draft_state or {}).get("_report_artifact_sink")
            if sink is None:
                raise ValueError(
                    "REPORT_CHART_CAPTURE_FAILED: an artifact sink is required"
                )
            data["_engine_extra_charts"] = prepare_option_charts(
                extra_spec, artifacts, sink
            )
            artifacts = list(sink.snapshot())
        except (ValueError, TypeError, OSError, KeyError) as error:
            errors.append({"json_path": "$.data.REPORT_CHARTS", "error": str(error)})
    if contract["mode"] == "placeholders":
        for field in contract["prose_fields"]:
            if not data.get(field):
                errors.append(
                    {
                        "json_path": f"$.data.{field}",
                        "error": (
                            "REPORT_REQUIREMENT_MISSING: fill the template "
                            "prose placeholder "
                        )
                        + field
                        + " using captured analysis; pass it directly in data, "
                        "preserve the existing fields and do not rerun analysis.",
                    }
                )
    if "REPORT_SPEC" in data:
        try:
            data["REPORT_SPEC"] = _use_methodology_notes(
                validate_report_spec(data["REPORT_SPEC"]), artifacts
            )
        except ValueError as error:
            errors.append({"json_path": "$.data.REPORT_SPEC", "error": str(error)})
    unavailable = [] if allow_unavailable_references else None
    if (
        not errors
        and isinstance(data.get("REPORT_SPEC"), dict)
        and draft_state is not None
    ):
        from .report_charts import (
            analysis_groups,
            missing_analysis_groups,
            prepare_report_charts,
        )

        missing = missing_analysis_groups(
            data["REPORT_SPEC"],
            draft_state.get("_report_analysis_groups", analysis_groups(artifacts)),
        )
        if missing:
            errors.append(
                {
                    "json_path": "$.data.REPORT_SPEC.sections",
                    "error": (
                        "REPORT_REQUIREMENT_MISSING: analysis sections are missing; "
                    )
                    + json.dumps(missing, ensure_ascii=False)
                    + ". Append interpretations and tables/charts using these captured "
                    "sources. "
                    "Recommendations alone do not cover an analysis task. Do not "
                    "rerun analysis.",
                }
            )
        if not missing:
            try:
                data["REPORT_SPEC"] = prepare_report_charts(
                    data["REPORT_SPEC"],
                    artifacts,
                    draft_state.get("_report_artifact_sink"),
                    language=draft_state.get("_report_language", "zh"),
                )
            except (ValueError, TypeError, OSError, KeyError) as error:
                errors.append(
                    {"json_path": "$.data.REPORT_SPEC.sections", "error": str(error)}
                )
            sink = draft_state.get("_report_artifact_sink")
            if sink is not None:
                artifacts = list(sink.snapshot())
    if allow_unavailable_references and isinstance(data.get("REPORT_SPEC"), dict):
        spec_error = _spec_evidence_error(data["REPORT_SPEC"], artifacts)
        if spec_error and spec_error.startswith("REPORT_TEMPLATE_SPEC_INVALID:"):
            targets, _ = json.JSONDecoder().raw_decode(
                spec_error.partition(":")[2].lstrip()
            )
            # Preserve the saved spec, and never rewrite HTML, identities or
            # table values. Only plain authored narrative may lose its number.
            eligible = [
                target
                for target in targets
                if ".table." not in target["json_path"]
                and not re.search(r"<\s*(?:[A-Za-z!/?]|$)", target["text"])
            ]
            if eligible:
                data = json.loads(json.dumps(data, ensure_ascii=False))
                for target in eligible:
                    path = [
                        name or int(index)
                        for name, index in re.findall(
                            r"\.([A-Za-z_][\w]*)|\[(\d+)\]",
                            target["json_path"][1:],
                        )
                    ]
                    parent = {"data": data}
                    for key in path[:-1]:
                        parent = parent[key]
                    values = set(target["values"])
                    parent[path[-1]] = _NUMERIC_CLAIM_PATTERN.sub(
                        lambda match: "--" if match[0] in values else match[0],
                        parent[path[-1]],
                    )
                unavailable.extend(eligible)
    resolved = _resolve_template_references(
        data, artifacts, errors=errors, unavailable_references=unavailable
    )
    if draft_state is not None:
        draft_state["_report_unavailable_references"] = unavailable or []
    spec = data.get("REPORT_SPEC")
    if isinstance(spec, dict) and isinstance(spec.get("sections"), list):
        for index, section in enumerate(spec["sections"]):
            chart = section.get("chart") if isinstance(section, dict) else None
            if (
                isinstance(chart, dict)
                and chart.get("renderer") == "echarts"
                and not re.search(r"\becharts\.init\s*\(", template)
            ):
                errors.append(
                    {
                        "json_path": f"$.data.REPORT_SPEC.sections[{index}].chart",
                        "error": (
                            "REPORT_TEMPLATE_CHART_INVALID: this template has no "
                            "ECharts "
                            "bootstrap. Reuse the existing ECharts template/data "
                            "renderer, "
                            "or select a captured native/image chart with refs. "
                            "An empty "
                            "host is not a rendered "
                            "chart."
                        ),
                    }
                )
    spec_error = _spec_evidence_error(spec, artifacts)
    if spec_error:
        errors.append({"json_path": "$.data.REPORT_SPEC", "error": spec_error})
    if (
        isinstance(spec, dict)
        and isinstance(spec.get("sections", []), list)
        and isinstance(required_recommendations, int)
    ):
        found = sum(
            len(section.get("recommendations") or [])
            for section in spec.get("sections") or []
            if isinstance(section, dict)
            and re.search(
                r"建议|recommend|action", str(section.get("heading") or ""), re.I
            )
        )
        if found < required_recommendations:
            errors.append(
                {
                    "json_path": "$.data.REPORT_SPEC.sections",
                    "error": (
                        "REPORT_REQUIREMENT_MISSING: "
                        "found="
                        f"{found}"
                        ", required="
                        f"{required_recommendations}"
                        "; "
                        "append concrete recommendations under a heading "
                        "containing 建议 "
                        "or recommendations."
                    ),
                }
            )
    if errors:
        if draft_state is not None:
            draft_state.pop("_report_draft", None)
            draft = _build_spec_draft(template, data, artifacts)
            if draft:
                draft_state["_report_draft"] = {
                    "status": "draft",
                    "title": "分析报告草稿（未完成）",
                    "content": draft,
                    "errors": errors,
                }
        only_requirement = all(
            item["error"].startswith("REPORT_REQUIREMENT_MISSING:") for item in errors
        )
        code = (
            "REPORT_REQUIREMENT_MISSING"
            if only_requirement
            else "REPORT_TEMPLATE_PREFLIGHT_INVALID"
        )
        raise ValueError(code + ": " + json.dumps(errors, ensure_ascii=False))
    data = resolved
    sources = _template_result_sources(artifacts)
    # A template payload can be supplied as a reference instead of being copied
    # by the model. Respect that producer even if another run has the same field.
    by_id = {artifact.artifact_id: artifact for artifact in artifacts}
    for key, value in data.items():
        if not isinstance(value, dict) or "value" not in value:
            continue
        selector = value.get("selector") or {}
        artifact = by_id.get(value.get("artifact_id"))
        if artifact and selector.get("field") == key and not selector.get("path"):
            sources[key] = {
                "artifact_id": artifact.artifact_id,
                "field": key,
                "value": value["raw"],
            }
    data = {**{key: source["value"] for key, source in sources.items()}, **data}
    if "{%" in template:
        # Expand data-driven DOM targets before assigning their persisted IDs.
        # Existing uppercase placeholders still use the provenance-aware path.
        template_data = dict(data)
        for key, value in template_data.items():
            if (
                isinstance(value, dict)
                and value.get("artifact_id")
                and (value.get("selector") or {}).get("field") == key
                and not (value.get("selector") or {}).get("path")
                and "raw" in value
            ):
                value = template_data[key] = value["raw"]
            if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
                try:
                    parsed = json.loads(value)
                except ValueError:
                    continue
                template_data[key] = _resolve_template_references(parsed, artifacts)
                if key == "REPORT_SPEC":
                    spec_error = _spec_evidence_error(template_data[key], artifacts)
                    if spec_error:
                        raise ValueError(spec_error)
        environment = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
        environment.globals.clear()
        try:
            template = environment.from_string(
                re.sub(
                    r"\{\{[A-Z_0-9]+\}\}",
                    lambda match: "{% raw %}" + match.group(0) + "{% endraw %}",
                    template,
                )
            ).render(template_data=template_data)
        except Exception as error:
            # A spec with the wrong shape (for example ``table`` as a string)
            # must name the contract instead of leaking a Jinja attribute error.
            raise ValueError(
                "REPORT_TEMPLATE_SPEC_INVALID: attribute=data; "
                f"{type(error).__name__}: {error}. Every section uses the documented "
                "block shapes (skills/business-report/SKILL.md): sections/kpis are "
                "objects, table/chart/note are objects, parts are lists of strings or "
                "reference nodes."
            ) from error
    results = {
        artifact.artifact_id: getattr(getattr(artifact, "result", None), "inline", None)
        for artifact in artifacts
        if getattr(artifact, "status", None) == "succeeded"
    }
    stack: List[str] = []
    tokens = html_tokens(template)
    output = []
    for token in tokens:
        is_tag = (
            token.startswith("<")
            and not set(stack).intersection({"script", "style"})
            or bool(re.match(r"</(?:script|style)\s*>", token, re.I))
        )
        if is_tag:
            closing = re.match(r"</\s*([\w:-]+)", token)
            opening = re.match(r"<\s*([\w:-]+)\b", token)
            if closing and closing.group(1).lower() in stack:
                index = len(stack) - 1 - stack[::-1].index(closing.group(1).lower())
                del stack[index:]
            elif opening:
                tag = opening.group(1).lower()
                if not token.rstrip().endswith("/>") and tag not in {
                    "img",
                    "br",
                    "hr",
                    "input",
                    "meta",
                    "link",
                    "source",
                    "wbr",
                }:
                    stack.append(tag)

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key.startswith("ARTIFACT_ID_"):
                field = key[len("ARTIFACT_ID_") :]
                source = sources.get(field)
                supplied = data.get(field)
                if isinstance(supplied, dict) and "value" in supplied:
                    supplied = supplied["raw"]
                if not source or supplied != source["value"]:
                    raise ValueError(
                        "REPORT_TEMPLATE_BINDING_INVALID: "
                        "attribute=data-dbgpt-artifacts;"
                        " "
                        "placeholder="
                        f"{key}"
                        "; expected a captured result field "
                        f"{field}"
                        " matching template "
                        "data"
                    )
                return source["artifact_id"]
            raw_value = data.get(key, "")
            if (
                contract["mode"] == "placeholders"
                and isinstance(raw_value, (list, dict))
                and key != "CHART_DATA_JSON"
                and not is_tag
                and not set(stack).intersection({"script", "style", "title"})
            ):
                return _render_placeholder_parts(raw_value)
            if (
                isinstance(raw_value, dict)
                and raw_value.get("artifact_id")
                and "value" in raw_value
            ):
                if set(stack).intersection({"script", "style"}):
                    value = raw_value["raw"]
                    serialized = (
                        json.dumps(value, ensure_ascii=False)
                        if isinstance(value, (dict, list))
                        else str(value)
                    )
                    return (
                        serialized.replace("<", r"\u003c")
                        .replace(">", r"\u003e")
                        .replace("&", r"\u0026")
                    )
                if is_tag or "title" in stack:
                    # Attributes and titles contain text, not inline evidence
                    # elements. In particular, keep image URLs intact so the
                    # chart binder can match their captured ChartArtifact.
                    return escape_html(str(raw_value["value"]), quote=True)
                return _result_span(
                    escape_html(str(raw_value["value"])),
                    raw_value["artifact_id"],
                    source_selector=raw_value.get("selector"),
                )
            value = (
                json.dumps(raw_value, ensure_ascii=False)
                if isinstance(raw_value, (dict, list))
                else str(raw_value)
            )
            source = sources.get(key, {})
            artifact_id, field = source.get("artifact_id"), source.get("field")
            result = results.get(artifact_id)
            if (
                not is_tag
                and not set(stack).intersection(_NUMERIC_CLAIM_SKIP_TAGS | {"title"})
                and _result_number(value)
                and isinstance(result, dict)
                and field in result
                and str(result[field]) == value
                and str(source.get("value")) == value
                and key not in {"YEAR", "REPORT_YEAR"}
            ):
                return _result_span(escape_html(value), artifact_id, field)
            if "script" in stack:
                return (
                    value.replace("<", r"\u003c")
                    .replace(">", r"\u003e")
                    .replace("&", r"\u0026")
                )
            if is_tag or set(stack).intersection({"style", "title"}):
                return escape_html(value, quote=True)
            return validate_template_fragment(value)

        output.append(re.sub(r"\{\{([A-Z_0-9]+)\}\}", replace, token))
    html = "".join(output)
    if data.get("_engine_extra_charts"):
        from .report_chart_options import append_extra_charts

        html = append_extra_charts(html, data["_engine_extra_charts"]["sections"])
    return html


def _normalize_report_chart_nodes(spec: Any, artifacts: List[Any]) -> Any:
    """Normalize whole charts and producers using captured outputs and lineage.

    A ChartArtifact root has no result to select. For exactly one such node in
    a section without a chart block, its identity and output determine the
    existing chart representation; no number, chart or evidence is invented.
    Field/path selections and multiple competing charts remain explicit errors.
    """
    if not isinstance(spec, dict) or not isinstance(spec.get("sections"), list):
        return spec
    charts = {
        item.artifact_id: item
        for item in artifacts
        if item.type == "chart" and item.status == "succeeded"
    }
    producers = {
        item.artifact_id: item
        for item in artifacts
        if item.type in {"python", "sql"} and item.status == "succeeded"
    }

    def normalize_chart(node):
        if not isinstance(node, dict) or node.get("renderer") or node.get("img"):
            return node
        refs = node.get("refs", [])
        if not isinstance(refs, list) or any(ref not in producers for ref in refs):
            return node
        # Use captured lineage, never names, captions or a guessed image path.
        outputs = [
            chart
            for chart in charts.values()
            if set(refs).intersection(chart.input_artifact_ids)
            and (
                (chart.chart_type == "image" and getattr(chart.output, "uri", None))
                or chart.execution.action == "chart_action.render"
            )
        ]
        if len(outputs) == 1:
            return {
                **node,
                "refs": list(dict.fromkeys([*refs, outputs[0].artifact_id])),
            }
        if len(refs) == 1:
            try:
                option = read_artifact_result(producers[refs[0]])
                selector = {"path": []}
                if isinstance(option, dict) and len(option) == 1:
                    field, value = next(iter(option.items()))
                    if isinstance(value, str):
                        value = json.loads(value)
                    if isinstance(value, dict):
                        option, selector = value, {"field": field}
                if (
                    isinstance(option, dict)
                    and isinstance(option.get("series"), list)
                    and option["series"]
                    and all(isinstance(series, dict) for series in option["series"])
                ):
                    return {
                        **node,
                        "renderer": "echarts",
                        "producer": {"artifact_id": refs[0], **selector},
                    }
            except (ValueError, TypeError, OSError):
                pass
        return node

    sections = []
    for section in spec["sections"]:
        if not isinstance(section, dict):
            sections.append(section)
            continue
        if section.get("chart"):
            sections.append({**section, "chart": normalize_chart(section["chart"])})
            continue
        found = []
        for key in _PROSE_KEYS:
            paragraphs = section.get(key)
            if not isinstance(paragraphs, list):
                continue
            for paragraph in paragraphs:
                if not isinstance(paragraph, list):
                    continue
                for node in paragraph:
                    if (
                        isinstance(node, dict)
                        and node.get("artifact_id") in charts
                        and set(node).issubset(_TEMPLATE_REFERENCE_KEYS)
                        and not any(
                            node.get(key)
                            for key in (
                                "field",
                                "path",
                                "kind",
                                "quote",
                                "proposal",
                                "format",
                                "suffix",
                            )
                        )
                    ):
                        chart = charts[node["artifact_id"]]
                        if (
                            getattr(chart.output, "uri", None)
                            or chart.execution.action == "chart_action.render"
                        ):
                            found.append(node)
        if len(found) != 1:
            sections.append(section)
            continue
        selected = found[0]
        chart = charts[selected["artifact_id"]]
        updated = dict(section)
        for key in _PROSE_KEYS:
            paragraphs = section.get(key)
            if isinstance(paragraphs, list):
                updated[key] = [
                    [node for node in paragraph if node is not selected]
                    if isinstance(paragraph, list)
                    else paragraph
                    for paragraph in paragraphs
                ]
        updated["chart"] = {
            "refs": list(dict.fromkeys([*chart.input_artifact_ids, chart.artifact_id])),
            "caption": section.get("heading") or chart.name or "分析图表",
        }
        if getattr(chart.output, "uri", None):
            updated["chart"]["img"] = chart.output.uri
        sections.append(updated)
    return {**spec, "sections": sections}


def _build_spec_draft(template: str, data: dict, artifacts: List[Any]) -> str | None:
    """Preview only independently valid blocks; never create a final presentation."""
    spec = data.get("REPORT_SPEC")
    if not isinstance(spec, dict):
        return None
    safe = {"title": "分析报告草稿（未完成）", "kpis": [], "sections": []}
    ids = [item.artifact_id for item in artifacts if item.status == "succeeded"]
    types = {
        item.artifact_id: item.type for item in artifacts if item.status == "succeeded"
    }

    def render(fragment):
        try:
            html = _render_template_with_bindings(
                template, {"REPORT_SPEC": fragment}, artifacts
            )
            html = _bind_generated_chart_images(html, artifacts)
            error = _validate_evidence_bindings(html, ids, (), (), types, artifacts)
            if error or validate_result_selectors(html, artifacts):
                return None
            return html
        except (ValueError, TypeError, OSError):
            return None

    for key in ("kpis", "sections"):
        items = spec.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            # Native/ECharts mounts require the final run's captured renderer.
            # Drafts have no report_id; don't preview an empty chart host.
            if isinstance(item, dict) and item.get("chart"):
                chart = item["chart"]
                chart_ids = chart.get("refs", []) if isinstance(chart, dict) else []
                if not any(
                    artifact.artifact_id in chart_ids
                    and artifact.type == "chart"
                    and getattr(getattr(artifact, "output", None), "uri", None)
                    for artifact in artifacts
                ):
                    continue
            if render({"title": safe["title"], key: [item]}):
                safe[key].append(item)
    if not safe["kpis"] and not safe["sections"]:
        return None
    html = render(safe)
    if not html:
        return None
    notice = (
        '<aside style="padding:16px;background:#fffbeb;border:1px solid '
        '#f59e0b">报告草稿：仅显示已通过证据校验的内容。其余内容仍待修复，正式报告尚未生成。</aside>'
    )
    return re.sub(
        r"(<body\b[^>]*>)", lambda match: match[0] + notice, html, count=1, flags=re.I
    )


def _bind_unwrapped_numeric_claims(html: str, artifacts: List[Any]) -> str:
    """Bind only result-backed numbers, excluding document and chart labels.

    A parent SQL binding alone cannot prove that every number inside it came from
    that query. Keep the original HTML and leave ambiguous numbers unbound.
    """
    artifact_by_id = {
        artifact.artifact_id: artifact
        for artifact in artifacts
        if getattr(artifact, "status", None) == "succeeded"
        and getattr(artifact, "type", None) in {"sql", "python"}
    }
    template_sources = _template_result_sources(artifacts)
    numeric_values = {}
    predicates = {}
    tokens = html_tokens(html)
    stack: List[Tuple[str, str | None, bool]] = []
    output: List[str] = []
    recent_text = ""

    def values_for(artifact_id):
        if artifact_id not in numeric_values:
            numeric_values[artifact_id] = _artifact_numeric_values(
                artifact_by_id[artifact_id]
            )
        return numeric_values[artifact_id]

    def predicates_for(artifact_id):
        if artifact_id not in predicates:
            predicates[artifact_id] = (
                sql_predicate_quotes(artifact_by_id[artifact_id])
                if artifact_id in artifact_by_id
                else []
            )
        return predicates[artifact_id]

    def source_for(ids: str | None, value: str) -> Tuple[str, str | None] | None:
        if not ids:
            fields = [
                source
                for source in template_sources.values()
                if source.get("artifact_id") in artifact_by_id
                and source["field"] not in {"YEAR", "REPORT_YEAR"}
                and _result_number(str(source.get("value")))
                and _matches_result_value(
                    value, {_result_number(str(source["value"]))[0]}
                )
            ]
            if len({source["artifact_id"] for source in fields}) == 1:
                return fields[0]["artifact_id"], fields[0]["field"] if len(
                    fields
                ) == 1 else None
            # Raw extraction results need not use template placeholder names.
            # Infer a source only when exactly one captured producer matches.
            matches = [
                artifact_id
                for artifact_id in artifact_by_id
                if _matches_result_value(value, values_for(artifact_id))
            ]
            if len(matches) == 1:
                artifact_id = matches[0]
                result = read_artifact_result(artifact_by_id[artifact_id])
                fields = (
                    [
                        key
                        for key, item in result.items()
                        if _result_number(str(item))
                        and _matches_result_value(value, {_result_number(str(item))[0]})
                    ]
                    if isinstance(result, dict)
                    else []
                )
                return artifact_id, fields[0] if len(fields) == 1 else None
        values = (
            [item.strip() for item in ids.split(",") if item.strip()] if ids else []
        )
        matches = [
            artifact_id
            for artifact_id in values
            if artifact_id in artifact_by_id
            and _matches_result_value(
                value,
                values_for(artifact_id),
                percent_scale=True,
            )
        ]
        if len(matches) != 1:
            return None
        artifact_id = matches[0]
        inline = getattr(
            getattr(artifact_by_id[artifact_id], "result", None), "inline", None
        )
        field = (
            next(iter(inline))
            if isinstance(inline, dict) and len(inline) == 1
            else None
        )
        return artifact_id, field

    for token in tokens:
        if not token:
            continue
        raw_text = any(tag in {"script", "style"} for tag, _, _ in stack)
        if token.startswith("<") and (
            not raw_text or re.match(r"</(?:script|style)\s*>", token, re.I)
        ):
            closing = re.match(r"</\s*([\w:-]+)", token)
            if closing:
                closing_tag = closing.group(1).lower()
                for index in range(len(stack) - 1, -1, -1):
                    if stack[index][0] == closing_tag:
                        del stack[index:]
                        break
                if closing_tag in {
                    "p",
                    "li",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "figcaption",
                    "caption",
                    "td",
                }:
                    recent_text = ""
            elif not token.startswith("<!--") and not token.startswith("<!"):
                opening = re.match(r"<\s*([\w:-]+)\b", token)
                if opening:
                    tag = opening.group(1).lower()
                    if re.fullmatch(r"h[1-6]", tag):
                        recent_text = ""
                    binding_match = next(iter_binding_tags(token), None)
                    parsed = parse_binding(binding_match) if binding_match else None
                    inherited = stack[-1][1] if stack else None
                    own_ids = ",".join(parsed["artifact_ids"]) if parsed else None
                    stack.append(
                        (
                            tag,
                            own_ids or inherited,
                            bool(
                                re.search(
                                    r"\bclass\s*=\s*(['\"])[^'\"]*\bsection-no\b[^'\"]*\1",
                                    token,
                                    re.IGNORECASE,
                                )
                                or (
                                    parsed
                                    and (
                                        tag in _INLINE_EVIDENCE_TAGS
                                        or parsed["attributes"].get(
                                            "data-dbgpt-target-kind"
                                        )
                                        == "claim"
                                    )
                                )
                            ),
                        )
                    )
                    if token.rstrip().endswith("/>") or tag in {
                        "img",
                        "br",
                        "hr",
                        "input",
                        "meta",
                        "link",
                        "source",
                        "wbr",
                    }:
                        stack.pop()
            output.append(token)
            continue

        inherited_ids = stack[-1][1] if stack else None
        if any(
            tag in _NUMERIC_CLAIM_SKIP_TAGS or bound_claim
            for tag, _, bound_claim in stack
        ):
            output.append(token)
            recent_text = (recent_text + unescape_html(token))[-80:]
            continue

        def bind(match: re.Match[str]) -> str:
            number = match.group(0)
            prefix = recent_text + unescape_html(token[: match.start()])
            if is_document_number(
                number,
                token[match.end() :],
                prefix,
                _NON_METRIC_NUMBER_PREFIX,
                heading=any(re.fullmatch(r"h[1-6]", tag) for tag, _, _ in stack),
            ):
                return number
            operator = re.search(r"(<=|>=|≤|≥|<|>|=)\s*$", prefix)
            if operator and inherited_ids:
                comparison = {"≤": "<=", "≥": ">="}.get(operator[1], operator[1])
                candidates = [
                    (artifact_id, quote)
                    for artifact_id in inherited_ids.split(",")
                    for sql_operator, literal, quote in predicates_for(artifact_id)
                    if sql_operator == comparison
                    and _result_number(literal) == _result_number(number)
                ]
                if len(candidates) == 1:
                    artifact_id, quote = candidates[0]
                    return _result_span(
                        number,
                        artifact_id,
                        source_selector={"kind": "sql", "quote": quote},
                    )
                return number
            source = source_for(inherited_ids, number)
            if not source:
                return number
            artifact_id, field = source
            return _result_span(number, artifact_id, field)

        output.append(_NUMERIC_CLAIM_PATTERN.sub(bind, token))
        recent_text = (recent_text + unescape_html(token))[-80:]
    return "".join(output)


def _use_methodology_notes(spec: Any, artifacts: List[Any]) -> Any:
    """Keep KB methodology in the section note, not duplicated in its intro."""
    if not isinstance(spec, dict):
        return spec
    knowledge_ids = {
        item.artifact_id
        for item in artifacts
        if item.status == "succeeded"
        and item.type == "reference"
        and item.reference_type == "knowledge"
    }
    sections = []
    for section in spec.get("sections", []):
        note = section.get("note") or {}
        if (note.get("ref") or {}).get("artifact_id") not in knowledge_ids:
            sections.append(section)
            continue
        intro = []
        method_section = re.search(
            r"口径|方法|数据说明|methodology|method", section.get("heading", ""), re.I
        )
        for paragraph in section.get("intro", []):
            references = [part for part in paragraph if isinstance(part, dict)]
            text = "".join(part for part in paragraph if isinstance(part, str)).strip()
            method_label = re.match(
                r"口径(?:提示|说明)|统计口径|方法说明|示例口径|Method(?:ology| note)",
                text,
                re.I,
            )
            only_knowledge = all(
                part.get("artifact_id") in knowledge_ids for part in references
            )
            if only_knowledge and (method_section or method_label or references):
                continue
            intro.append(paragraph)
        sections.append({**section, "intro": intro})
    return {**spec, "sections": sections}


def _bind_tables_from_cells(html: str, artifacts: List[Any]) -> str:
    """Aggregate captured cell sources without certifying other table values."""
    producers = {
        item.artifact_id
        for item in artifacts
        if item.status == "succeeded" and item.type in {"sql", "python", "reference"}
    }
    output = []
    tables = []
    for token in html_tokens(html):
        opening = re.match(r"<\s*([\w:-]+)\b", token)
        closing = re.match(r"</\s*([\w:-]+)", token)
        if opening:
            tag = opening[1].lower()
            binding_match = next(iter_binding_tags(token), None)
            binding = parse_binding(binding_match) if binding_match else None
            if tag == "table":
                tables.append(
                    {
                        "index": len(output),
                        "bound": bool(binding),
                        "cell": False,
                        "ids": [],
                    }
                )
            elif tables:
                table = tables[-1]
                if tag in {"td", "th"}:
                    table["cell"] = True
                if table["cell"] and binding:
                    for artifact_id in binding["artifact_ids"]:
                        if artifact_id in producers and artifact_id not in table["ids"]:
                            table["ids"].append(artifact_id)
        elif closing and tables:
            tag = closing[1].lower()
            if tag in {"td", "th"}:
                tables[-1]["cell"] = False
            elif tag == "table":
                table = tables.pop()
                if not table["bound"] and table["ids"]:
                    index = table["index"]
                    output[index] = output[index][:-1] + (
                        ' data-dbgpt-artifacts="'
                        + escape_html(",".join(table["ids"]), quote=True)
                        + '">'
                    )
        output.append(token)
    return "".join(output)


def _collapse_nested_inline_evidence_bindings(html: str) -> str:
    """Keep one evidence target for a number wrapped by nested inline tags.

    A common LLM pattern is ``<b data-dbgpt-artifacts=...>750</b>``.  The
    numeric-claim normalizer correctly adds a ``<strong>`` so that the value
    itself has a stable target, but this can leave
    ``<b data-...><strong data-...>750</strong></b>`` behind.  It produces two
    report-schema claim blocks and two visible SQL pills for a single value.

    The innermost inline target is the most specific semantic object, so remove
    provenance attributes from any inline wrapper containing another bound
    inline target.  This deliberately does not change block/table/figure
    bindings: their broader SQL/KB provenance remains available on the card,
    table, or chart container.
    """
    inline_tags = "|".join(sorted(_INLINE_EVIDENCE_TAGS, key=len, reverse=True))
    outer_pattern = re.compile(
        rf"<(?P<tag>{inline_tags})\b(?P<attrs>[^>]*\bdata-dbgpt-artifacts\s*="
        rf"(?P<quote>['\"])[^'\"]+(?P=quote)[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    nested_pattern = re.compile(
        rf"<(?:(?:{inline_tags}))\b[^>]*\bdata-dbgpt-artifacts\s*=",
        re.IGNORECASE,
    )

    def collapse(match: re.Match) -> str:
        if not nested_pattern.search(match.group("body")):
            return match.group(0)
        attrs = match.group("attrs")
        for attribute in _REDUNDANT_INLINE_EVIDENCE_ATTRS:
            attrs = re.sub(
                rf"\s*\b{re.escape(attribute)}\s*=\s*(['\"])[^'\"]*\1",
                "",
                attrs,
                flags=re.IGNORECASE,
            )
        return (
            f"<{match.group('tag')}{attrs}>{match.group('body')}</{match.group('tag')}>"
        )

    # A model can add span > b > strong wrappers.  Iterate until every outer
    # wrapper has been normalized, with a small bound for malformed markup.
    for _ in range(8):
        collapsed = outer_pattern.sub(collapse, html)
        if collapsed == html:
            break
        html = collapsed
    return html


def _prepare_presentation_bindings(
    html: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Assign stable HTML target IDs and return their structured bindings."""
    html = normalize_binding_attributes(html)
    bindings: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _bind(match: re.Match) -> str:
        tag = match.group("tag")
        attrs = match.group("attrs")
        parsed = parse_binding(match)
        attributes = parsed["attributes"]
        if re.search(r"\bdata-dbgpt-evidence-summary\b", attrs, re.IGNORECASE):
            return match.group(0)
        explicit_kind = (attributes.get("data-dbgpt-target-kind") or "").lower()
        target_type = (
            "claim"
            if explicit_kind == "claim" or tag.lower() in _INLINE_EVIDENCE_TAGS
            else "block"
        )
        id_attribute = (
            "data-dbgpt-claim-id" if target_type == "claim" else "data-dbgpt-block-id"
        )
        target_id = attributes.get(id_attribute)
        if (
            not target_id
            or len(target_id) > 100
            or not re.fullmatch(r"[A-Za-z0-9_.:-]+", target_id)
            or target_id in seen_ids
        ):
            target_id = f"html-{target_type}-{len(bindings) + 1}"
            attrs += f' {id_attribute}="{target_id}"'
        seen_ids.add(target_id)
        artifact_ids = parsed["artifact_ids"]
        artifact_selectors = parsed["artifact_selectors"]
        label = attributes.get("data-dbgpt-evidence-label") or target_id
        bindings.append(
            {
                "target_id": target_id,
                "target_type": target_type,
                "label": label[:512],
                "artifact_ids": list(dict.fromkeys(artifact_ids)),
                "element_tag": tag.upper(),
                "artifact_selectors": artifact_selectors,
            }
        )
        return f"<{tag}{attrs}>"

    prepared_html = replace_binding_tags(html, _bind)
    texts = claim_target_texts(prepared_html)
    for binding in bindings:
        if binding["target_type"] == "claim":
            binding["text"] = texts.get(binding["target_id"], "")
            if not binding["text"]:
                raise BindingAttributeError(
                    "REPORT_ATTRIBUTE_INVALID: attribute=data-dbgpt-claim-id; "
                    "container="
                    f"{binding['target_id']}"
                    "; claim target must contain visible "
                    "text"
                )
        if binding["label"] != binding["target_id"]:
            continue
        id_attribute = (
            "data-dbgpt-claim-id"
            if binding["target_type"] == "claim"
            else "data-dbgpt-block-id"
        )
        content_match = re.search(
            rf"<(?P<tag>[a-zA-Z][\w:-]*)\b[^>]*\b{id_attribute}\s*=\s*"
            rf"(['\"]){re.escape(binding['target_id'])}\2[^>]*>"
            rf"(?P<body>.*?)</(?P=tag)\s*>",
            prepared_html,
            re.IGNORECASE | re.DOTALL,
        )
        if content_match:
            content = re.sub(r"<[^>]+>", " ", content_match.group("body"))
            content = " ".join(unescape_html(content).split())
            if content:
                binding["label"] = content[:512]
    return prepared_html, bindings


def _mark_unbound_report_numbers(html: str, error: str | None):
    """Last-resort delivery marks unverified prose values, never substitutes data.

    Unbound or mismatched prose numbers become unavailable instead of being
    presented as facts. Bad identities, selectors, charts and tables still
    require a proper repair.
    """
    if not error or not error.startswith("REPORT_TARGET_BINDING_REQUIRED:"):
        return html, []
    try:
        targets, _ = json.JSONDecoder().raw_decode(error.partition(":")[2].lstrip())
    except ValueError:
        return html, []
    if not targets or any(
        target.get("kind") not in {"numeric_value", "numeric_source_mismatch"}
        for target in targets
    ):
        return html, []
    replacements = {}
    for target in targets:
        offset, old = target.get("html_offset"), target.get("old")
        if not isinstance(offset, int) or not isinstance(old, str):
            return html, []
        if html[offset : offset + len(old)] != old:
            return html, []
        values = replacements.setdefault((offset, old), set())
        values.add(target["value"])
        if target["kind"] == "numeric_value":
            # The validator coalesces repeated targets in one text node. Every
            # measured value in this unbound node needs the same treatment.
            text = unescape_html(old)
            values.update(
                match[0]
                for match in _NUMERIC_CLAIM_PATTERN.finditer(text)
                if not is_document_number(
                    match[0],
                    text[match.end() :],
                    text[: match.start()],
                    _NON_METRIC_NUMBER_PREFIX,
                )
            )
            target["values"] = sorted(values)
    for (offset, old), values in sorted(replacements.items(), reverse=True):
        text = unescape_html(old)
        marked = _NUMERIC_CLAIM_PATTERN.sub(
            lambda match: "--" if match[0] in values else match[0], text
        )
        marked = escape_html(marked)
        html = html[:offset] + marked + html[offset + len(old) :]
    return html, targets


def make_html_interpreter(
    react_state: Dict[str, Any],
    skills_dir: str,
    *,
    business_spec_only: bool = False,
    allow_unavailable_references: bool = False,
):
    @tool(
        description=(
            "For non-financial reports. Annual financial reports use the dedicated "
            "financial tools and built-in report component instead. "
            "Render a complete styled HTML analysis report using html, or "
            "existing template_path/data. "
            "Use head/style for CSS. Long reports should reuse templates. "
            "Every number needs a local SQL/Python result binding; tables "
            "need their own source. "
            "KB rules bind real captured slice IDs; quote is optional and "
            "must match if provided. "
            "HTML-escape selector JSON quote characters (&#39; for SQL "
            "apostrophes in single-quoted attributes). "
            "Result selectors use field for the actual result key and path "
            "as an array, "
            'for example {"field":"CHART_DATA_JSON","path":["driver_analysis"'
            ',"items",1,"corr"]}. '
            "Each chart binds its own captured ChartArtifact. Existing "
            "ECharts templates may declare "
            "a figure with data-dbgpt-chart-renderer=echarts, a producer "
            "binding and an exact "
            "result field/path selector. The bound figure needs id or "
            "data-dbgpt-block-id; "
            "its child chart host needs id. The renderer supplies the chart ID. "
            "report_evidence_manifest provides real IDs and binding "
            "examples; reuse unchanged selections. "
            "After failure, keep completed analysis and saved HTML/styles. "
            "Read pending.html at the "
            "reported location, then call retry_saved=true with "
            "repair_patches=[{old:exact original, "
            "new:replacement, html_offset:optional offset}] for all affected targets. "
            "All patches use the same saved document; merge overlaps and "
            "provide complete JSON. "
            "For truncation, old is the exact tail_anchor and new is that "
            "anchor plus the missing remainder. "
            "Template repairs use retry_saved=true and only changed data fields. "
            "Follow retryable=false; do not resend full HTML or rerun "
            "completed analysis. "
            "Template {{ARTIFACT_ID_field}} placeholders resolve actual "
            "captured result producers. "
            'Template data values may also be {"artifact_id",'
            '"field"/"path"} references; the renderer resolves, formats and '
            "binds them, so a template report never needs a hand-typed number. "
            "Pass `data` as a JSON object, never as an escaped JSON string. "
            "When the report succeeds and deliverables are complete, call terminate."
        )
    )
    @report_repair_guard(react_state)
    async def html_interpreter(
        html: str = "",
        title: str = "Report",
        file_path: str = "",
        template_path: str = "",
        data: Dict[str, Any] | None = None,
        retry_saved: bool = False,
        repair_patches: List[Dict[str, Any]] | None = None,
    ) -> str:
        """Render HTML as an interactive web report."""
        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        # Keep terminal handling honest: tool validation failures must not later
        # be exposed as a completed HTML report.
        react_state["_report_html_attempted"] = True
        react_state["_report_unavailable_references"] = []
        react_state.pop("_report_html_error", None)
        skills_path = Path(skills_dir).expanduser().resolve()

        # A template selected from ``skills_dir`` is reviewed application
        # content, rather than model-authored HTML.  Some shipped skill
        # templates (for example CSV analysis) render their data with ECharts
        # after the document loads.  Preserve this provenance as presentation
        # metadata so the browser can make the narrow script decision without
        # enabling scripts for ordinary ``html`` / ``file_path`` input.
        trusted_template_scripts = bool(template_path and template_path.strip())
        if retry_saved:
            trusted_template_scripts = react_state.get(
                "_report_saved_template_scripts", False
            )
        else:
            react_state["_report_saved_template_scripts"] = trusted_template_scripts

        # ── Mode 1: template_path + data ──
        if template_path and template_path.strip():
            tp = template_path.strip()
            target = (skills_path / tp).resolve()
            try:
                target.relative_to(skills_path)
            except ValueError:
                raise ValueError(
                    (
                        "REPORT_TEMPLATE_INVALID: template_path escapes skills "
                        "directory: "
                        f"{tp}"
                    )
                )
            if not target.is_file():
                available = sorted(
                    path.relative_to(skills_path).as_posix()
                    for path in skills_path.rglob("templates/*.html")
                )[:8]
                raise ValueError(
                    f"REPORT_TEMPLATE_NOT_FOUND: template_path={tp}. Available "
                    "templates: " + (", ".join(available) or "none found") + ". "
                    "Pass the template file path (not its directory); reuse "
                    "completed artifacts."
                )
            try:
                raw_template = target.read_text(encoding="utf-8")
            except Exception as e:
                raise ValueError(
                    f"REPORT_TEMPLATE_READ_FAILED: template_path={tp}: {e}"
                ) from e

            react_state["_report_template_contract"] = report_template_contract(
                raw_template
            )

            replacements = data
            if isinstance(replacements, str):
                try:
                    replacements = json.loads(replacements)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        (
                            "REPORT_TEMPLATE_DATA_INVALID: attribute=data; JSON line "
                            f"{e.lineno}"
                            ", column "
                            f"{e.colno}"
                            ", position "
                            f"{e.pos}"
                            ": "
                            f"{e.msg}"
                            ". Fix only data; reuse template_path and completed "
                            "artifacts."
                        )
                    ) from e
            if replacements is None:
                replacements = {}
            elif not isinstance(replacements, dict):
                raise ValueError(
                    "REPORT_TEMPLATE_DATA_INVALID: attribute=data must be a JSON object"
                )

            auto_data = react_state.get("auto_data", {})
            if isinstance(auto_data, dict):
                replacements = {**auto_data, **replacements}

            image_url_map = react_state.get("image_url_map", {})
            if isinstance(image_url_map, dict):
                for stem, url in image_url_map.items():
                    chart_key = f"CHART_{stem.upper()}"
                    if chart_key not in replacements:
                        replacements[chart_key] = url

            sink = react_state.get("_report_artifact_sink")
            replacements = _merge_report_spec(replacements, react_state)
            spec = replacements.get("REPORT_SPEC")
            if isinstance(spec, dict):
                spec["language"] = (
                    "en" if react_state.get("_report_language") == "en" else "zh"
                )
            html = _render_template_with_bindings(
                raw_template,
                replacements,
                sink.snapshot() if sink is not None else [],
                required_recommendations=react_state.get(
                    "_report_required_recommendation_count"
                ),
                draft_state=react_state,
                allow_unavailable_references=allow_unavailable_references,
            )
            if not title or title == "Report":
                title = target.stem

        # ── Mode 2: file_path ──
        elif file_path and file_path.strip():
            fp = file_path.strip()
            if not os.path.isfile(fp):
                cid = react_state.get("conv_id") or "default"
                from dbgpt.configs.model_config import PILOT_PATH

                alt = os.path.join(PILOT_PATH, "data", cid, os.path.basename(fp))
                if os.path.isfile(alt):
                    fp = alt
                else:
                    raise ValueError(
                        f"REPORT_FILE_NOT_FOUND: attribute=file_path; file={file_path}"
                    )
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    html = f.read()
                if not title or title == "Report":
                    title = os.path.splitext(os.path.basename(fp))[0]
            except Exception as e:
                raise ValueError(
                    (
                        "REPORT_FILE_READ_FAILED: attribute=file_path; "
                        "file="
                        f"{file_path}"
                        ": "
                        f"{e}"
                    )
                ) from e

        # A tool-call argument can be a syntactically valid JSON string while
        # its HTML value still contains JavaScript-style string delimiters.
        # Normalize before document/evidence validation so the persisted
        # presentation and the live preview always use the same DOM.
        react_state["_report_attempt_phase"] = "render"
        html = _normalize_concatenated_html_literals(html)
        retain_html_candidate(react_state, html, title)

        if not html or not html.strip():
            raise ValueError(
                "HTML_DOCUMENT_EMPTY: attribute=html; no HTML content provided"
            )

        document_error = _validate_complete_html_document(html)
        if document_error:
            react_state["_report_html_error"] = document_error
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": document_error}]},
                ensure_ascii=False,
            )

        # Post-process: fix image URLs
        fixed_html = html.strip()
        try:
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
            name_to_served: Dict[str, str] = {}
            if os.path.isdir(STATIC_MESSAGE_IMG_PATH):
                for fname in os.listdir(STATIC_MESSAGE_IMG_PATH):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IMAGE_EXTS:
                        continue
                    m = re.match(r"^[0-9a-f]{8}_(.+)$", fname, re.IGNORECASE)
                    if m:
                        name_to_served[m.group(1).lower()] = f"/images/{fname}"

            if name_to_served:

                def _fix_img_src(match: re.Match) -> str:
                    prefix = match.group(1)
                    raw_path = match.group(2)
                    quote = match.group(3)
                    filename = raw_path.rsplit("/", 1)[-1].lower()
                    if re.match(r"^[0-9a-f]{8}_.+$", filename, re.IGNORECASE):
                        return match.group(0)
                    if filename in name_to_served:
                        return f"{prefix}{name_to_served[filename]}{quote}"
                    return match.group(0)

                fixed_html = re.sub(
                    r"""(src\s*=\s*["'])([^"']+\.(?:png|jpg|jpeg|gif|svg|webp))(["'])""",
                    _fix_img_src,
                    fixed_html,
                    flags=re.IGNORECASE,
                )
        except Exception:
            pass

        # Auto-append missing images
        try:
            gen_images = react_state.get("generated_images", [])
            if gen_images:
                html_img_stems = set(
                    re.sub(r"^[0-9a-f]+_", "", os.path.basename(src))
                    for src in re.findall(
                        r'<img[^>]+src=["\']([^"\']+)["\']', fixed_html, re.IGNORECASE
                    )
                )

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
                        f'style="max-width:100%;height:auto;border-radius:8px">'
                        f"</div>"
                        for url in missing
                    )
                    section = (
                        '<div style="margin-top:32px"><h2>📊 分析图表</h2>'
                        f"{imgs_html}</div>"
                    )
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

        try:
            fixed_html = normalize_binding_attributes(fixed_html)
        except BindingAttributeError as error:
            candidate = error.html if error.html is not None else fixed_html
            retain_html_candidate(react_state, candidate, title)
            react_state["_report_html_error"] = str(error)
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": str(error)}]},
                ensure_ascii=False,
            )
        react_state["_report_pending_html"] = fixed_html
        react_state["_report_pending_title"] = title

        requirement_error = _validate_recommendation_requirement(
            fixed_html, react_state.get("_report_required_recommendation_count")
        )
        # Validate declared data sources before exposing the rendered report.
        try:
            artifact_sink = react_state.get("_report_artifact_sink")
            artifacts = artifact_sink.snapshot() if artifact_sink is not None else []
            fixed_html = _resolve_inline_report_references(fixed_html, artifacts)
            knowledge_search_error = _validate_requested_knowledge_search(
                react_state, artifacts
            )
            successful_artifact_ids = [
                artifact.artifact_id
                for artifact in artifacts
                if getattr(artifact, "status", "") == "succeeded"
            ]
            # A generated image is a concrete chart output.  If that image is
            # embedded in the report, it must expose its own chart artifact in
            # addition to the SQL data artifact; otherwise the Python/chart
            # provenance would disappear behind an apparently traceable figure.
            required_chart_artifact_ids = []
            for artifact in artifacts:
                if (
                    getattr(artifact, "status", "") != "succeeded"
                    or getattr(artifact, "type", "") != "chart"
                ):
                    continue
                output = getattr(artifact, "output", None)
                uri = getattr(output, "uri", None) if output is not None else None
                filename = os.path.basename(str(uri or "").split("?", 1)[0])
                if filename and filename in fixed_html:
                    required_chart_artifact_ids.append(artifact.artifact_id)
            fixed_html = _strip_ordinal_title_bindings(fixed_html)
            fixed_html = _bind_generated_chart_images(fixed_html, artifacts)
            fixed_html = _attach_native_charts_to_matching_tables(fixed_html, artifacts)
            fixed_html = capture_template_charts(fixed_html, artifact_sink)
            artifacts = artifact_sink.snapshot() if artifact_sink is not None else []
            successful_artifact_ids = [
                item.artifact_id for item in artifacts if item.status == "succeeded"
            ]
            fixed_html = normalize_payload_selectors(fixed_html, artifacts)
            fixed_html = _bind_unwrapped_numeric_claims(fixed_html, artifacts)
            fixed_html = _bind_tables_from_cells(fixed_html, artifacts)
            fixed_html = _collapse_nested_inline_evidence_bindings(fixed_html)
            selected_ids = {
                artifact_id
                for match in iter_binding_tags(fixed_html)
                for artifact_id in parse_binding(match)["artifact_ids"]
            }
            selected_native_chart_ids = [
                artifact.artifact_id
                for artifact in artifacts
                if artifact.artifact_id in selected_ids
                and getattr(artifact, "status", "") == "succeeded"
                and getattr(artifact, "type", "") == "chart"
                and getattr(getattr(artifact, "execution", None), "action", "")
                == "chart_action.render"
            ]
            # Error anchors must refer to the exact candidate used for repairs,
            # including separator normalization and existing HTML transforms.
            react_state["_report_pending_html"] = fixed_html
            react_state["_report_last_attempt_html"] = fixed_html
            knowledge_reference_artifacts = {
                artifact.artifact_id: artifact
                for artifact in artifacts
                if getattr(artifact, "status", "") == "succeeded"
                and getattr(artifact, "type", "") == "reference"
                and getattr(artifact, "reference_type", "") == "knowledge"
            }
            knowledge_source_error = (
                await asyncio.to_thread(
                    validate_knowledge_sources,
                    fixed_html,
                    knowledge_reference_artifacts,
                )
                if knowledge_reference_artifacts
                else None
            )
            knowledge_quote_error = _validate_kb_excerpt_quotes(
                fixed_html, knowledge_reference_artifacts
            )
            knowledge_binding_error = _validate_requested_knowledge_bindings(
                fixed_html, react_state, knowledge_reference_artifacts
            )
            warnings = []
            if not DEFAULT_TRACEABLE_REPORT_POLICY.strict_knowledge_requirements:
                warnings = [
                    error
                    for error in (
                        knowledge_search_error,
                        knowledge_binding_error
                        if not react_state.get("_report_require_knowledge_bindings")
                        else None,
                    )
                    if error
                ]
                knowledge_search_error = None
                if not react_state.get("_report_require_knowledge_bindings"):
                    knowledge_binding_error = None
            unavailable = react_state.get("_report_unavailable_references", [])
            if unavailable:
                warnings.append(
                    "REPORT_REFERENCE_UNAVAILABLE: "
                    + json.dumps(unavailable, ensure_ascii=False)
                )
            # Validate captured identities without silently removing a bad citation.
            # Full-file reads already produce independent chunk artifacts.
            binding_error = _validate_evidence_bindings(
                fixed_html,
                successful_artifact_ids,
                required_chart_artifact_ids,
                # Exploratory charts remain optional. Every chart selected by
                # a report binding must have its own renderable figure.
                selected_native_chart_ids,
                {
                    artifact.artifact_id: getattr(artifact, "type", "")
                    for artifact in artifacts
                    if getattr(artifact, "status", "") == "succeeded"
                },
                artifacts,
            )
            if allow_unavailable_references:
                marked_targets = []
                # A bound node can contain both matching and mismatched values.
                # Validation reports one target per node; repeat only while the
                # deterministic replacement makes progress, with a fixed cap.
                for _ in range(20):
                    marked, unbound = _mark_unbound_report_numbers(
                        fixed_html, binding_error
                    )
                    if not unbound or marked == fixed_html:
                        break
                    fixed_html = marked
                    marked_targets.extend(unbound)
                    binding_error = _validate_evidence_bindings(
                        fixed_html,
                        successful_artifact_ids,
                        required_chart_artifact_ids,
                        selected_native_chart_ids,
                        {
                            item.artifact_id: item.type
                            for item in artifacts
                            if item.status == "succeeded"
                        },
                        artifacts,
                    )
                if marked_targets:
                    unavailable.extend(marked_targets)
                    warnings.append(
                        "REPORT_NUMERIC_VALUE_UNAVAILABLE: "
                        + json.dumps(marked_targets, ensure_ascii=False)
                    )
                    react_state["_report_pending_html"] = fixed_html
                    react_state["_report_last_attempt_html"] = fixed_html
            binding_error = (
                "\n".join(
                    error
                    for error in (
                        binding_error,
                        validate_result_selectors(fixed_html, artifacts),
                        knowledge_search_error,
                        knowledge_source_error,
                        knowledge_quote_error,
                        knowledge_binding_error,
                        requirement_error,
                    )
                    if error
                )
                or None
            )
            if binding_error:
                react_state["_report_html_error"] = binding_error
                return json.dumps(
                    {"chunks": [{"output_type": "text", "content": binding_error}]},
                    ensure_ascii=False,
                )
            if warnings:
                english = react_state.get("_report_language") == "en"
                source_note = (
                    "Source note: This report presents completed analysis results. "
                    if english
                    else "来源说明：本报告展示已完成的分析结果。"
                )
                if any(
                    "chart" not in item and "citation" not in item
                    for item in unavailable
                ):
                    source_note += (
                        "Some numeric claims could not be verified and are marked --. "
                        if english
                        else "部分文字数值的来源路径无法核验，已标为 --，"
                        "相关结论需复核。"
                    )
                if any("chart" in item for item in unavailable):
                    source_note += (
                        "Some charts were unavailable; verified analysis "
                        "and tables remain. "
                        if english
                        else "部分图表未生成或无法绑定，已省略；"
                        "对应分析及已核验表格保留。"
                    )
                if any("citation" in item for item in unavailable):
                    source_note += (
                        "Some quotations differed from their sources; captured text "
                        "and source links were retained. "
                        if english
                        else "部分引文与原文不一致，已使用捕获原文并保留对应来源链接。"
                    )
                if any(error.startswith(("KNOWLEDGE_", "KB_")) for error in warnings):
                    source_note += (
                        "Knowledge-base definitions or citations remain incomplete; "
                        "please review them. "
                        if english
                        else "知识库口径的检索或逐项引用尚不完整，相关口径请复核。"
                    )
                notice = (
                    '<aside class="report-source-notice" style="padding:12px 16px;'
                    'margin:16px;background:#fffbeb;border-left:4px solid #f59e0b">'
                    + source_note
                    + "</aside>"
                )
                fixed_html = re.sub(
                    r"</body\s*>",
                    lambda _: notice + "</body>",
                    fixed_html,
                    count=1,
                    flags=re.I,
                )
            react_state["_report_warnings"] = warnings
            fixed_html, presentation_bindings = _prepare_presentation_bindings(
                fixed_html
            )
            react_state["_report_presentation_bindings"] = presentation_bindings
            react_state["_report_presentation"] = {
                "format": "html",
                "title": title,
                "content": fixed_html,
                "sha256": hashlib.sha256(fixed_html.encode("utf-8")).hexdigest(),
                "binding_count": len(presentation_bindings),
                "trusted_template_scripts": trusted_template_scripts,
                "warnings": warnings,
            }
            react_state.pop("_report_html_error", None)
            react_state.pop("_report_draft", None)
        except BindingAttributeError as error:
            candidate = error.html if error.html is not None else fixed_html
            retain_html_candidate(react_state, candidate, title)
            raise
        except Exception:
            logger.exception("Unable to prepare structured report evidence bindings")
            react_state["_report_html_error"] = (
                "TRACEABILITY_BINDING_ERROR: The report evidence mapping could not "
                "be prepared."
            )
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                "TRACEABILITY_BINDING_ERROR: The report evidence "
                                "mapping could not be prepared. Keep the completed "
                                "analysis results and report this system error; do not "
                                "rerun successful SQL or Python steps."
                            ),
                        }
                    ]
                },
                ensure_ascii=False,
            )

        chunks: List[Dict[str, Any]] = [
            {
                "output_type": "text",
                "content": (
                    "HTML 报告已成功渲染并展示给用户。报告任务已完成，"
                    "请勿重复调用 html_interpreter 生成报告。"
                    "若全部目标已达成，请直接调用 terminate 结束。"
                ),
            },
            {"output_type": "html", "content": fixed_html, "title": title},
        ]
        response = json.dumps(
            {
                "status": "completed",
                "retryable": False,
                "chunks": chunks,
                "warnings": warnings,
            },
            ensure_ascii=False,
        )
        react_state["_report_success_response"] = response
        return response

    if business_spec_only:
        parameter = html_interpreter._tool.args["data"]
        parameter.json_schema = report_data_schema()
        # Legacy ReAct prompts read type, while native calls read json_schema.
        # Both must expose the same contract generated from the one model.
        parameter.type = json.dumps(parameter.json_schema, ensure_ascii=False)
    return html_interpreter
