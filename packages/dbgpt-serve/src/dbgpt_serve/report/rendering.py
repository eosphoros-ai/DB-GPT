"""Read-only, resource-bounded report preview renderer."""

from __future__ import annotations

import html
import math
from typing import Any, Dict, List, Tuple

from dbgpt.core.interface.report import (
    Artifact,
    ChartBlock,
    InsightBlock,
    MetricBlock,
    ReportDocument,
    TableBlock,
    TextBlock,
)
from dbgpt.core.interface.report_html import normalize_report_html

MAX_RENDER_TABLE_ROWS = 20
MAX_RENDER_TABLE_COLUMNS = 10
MAX_RENDER_TEXT_CHARS = 100_000
MAX_RENDER_CELL_CHARS = 500
MAX_RENDER_OUTPUT_CHARS = 4_000_000
MAX_RENDER_BLOCKS = 100
MAX_RENDER_SECTIONS = 50
MAX_RENDER_EVIDENCE = 50
MAX_RENDER_ARTIFACT_INDEX = 5_000
MAX_RENDER_PRESENTATION_CHARS = 500_000
_MAX_STRUCTURED_ITEMS = 20
_MAX_STRUCTURED_DEPTH = 3
_TRUNCATED = "[Content truncated for preview/export.]"
REPORT_PREVIEW_CSP = (
    "default-src 'none'; img-src 'self' data: blob:; "
    "style-src 'self' 'unsafe-inline'; font-src 'self' data:; frame-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class _RenderBuffer:
    def __init__(self, limit: int = MAX_RENDER_OUTPUT_CHARS) -> None:
        self._limit = limit
        self._size = 0
        self._parts: List[str] = []
        self.exhausted = False

    def append(self, value: str) -> bool:
        if self.exhausted:
            return False
        if self._size + len(value) > self._limit:
            marker = f"\n\n{_TRUNCATED}\n"
            if self._size + len(marker) <= self._limit:
                self._parts.append(marker)
            self.exhausted = True
            return False
        self._parts.append(value)
        self._size += len(value)
        return True

    def render(self) -> str:
        return "".join(self._parts)


def _bounded_text(value: str) -> str:
    if len(value) <= MAX_RENDER_TEXT_CHARS:
        return value
    return value[:MAX_RENDER_TEXT_CHARS] + f"\n\n{_TRUNCATED}"


def _bounded_cell(value: Any, depth: int = 0) -> str:
    """Format JSON-compatible values without materializing the full structure."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:MAX_RENDER_CELL_CHARS]
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return "[non-finite number]"
        return str(value)[:MAX_RENDER_CELL_CHARS]
    if depth >= _MAX_STRUCTURED_DEPTH:
        return "[structured value]"
    if isinstance(value, (list, tuple)):
        items = [
            _bounded_cell(item, depth + 1) for item in value[:_MAX_STRUCTURED_ITEMS]
        ]
        suffix = ", …" if len(value) > _MAX_STRUCTURED_ITEMS else ""
        return ("[" + ", ".join(items) + suffix + "]")[:MAX_RENDER_CELL_CHARS]
    if isinstance(value, dict):
        items = []
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_STRUCTURED_ITEMS:
                items.append("…")
                break
            items.append(
                f"{_bounded_cell(key, depth + 1)}: {_bounded_cell(item, depth + 1)}"
            )
        return ("{" + ", ".join(items) + "}")[:MAX_RENDER_CELL_CHARS]
    return f"[{type(value).__name__}]"


def _markdown_text(value: Any) -> str:
    return (
        _bounded_cell(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _evidence_line(block) -> str:
    artifact_ids: List[str] = []
    seen = set()
    for item in block.evidence:
        if item.artifact_id in seen:
            continue
        seen.add(item.artifact_id)
        artifact_ids.append(item.artifact_id)
        if len(artifact_ids) >= MAX_RENDER_EVIDENCE:
            break
    if not artifact_ids:
        return ""
    return "Evidence: " + ", ".join(
        f"`{_markdown_text(item)}`" for item in artifact_ids
    )


def _artifact_index(document: ReportDocument) -> Dict[str, Artifact]:
    return {
        artifact.artifact_id: artifact
        for artifact in document.artifacts[:MAX_RENDER_ARTIFACT_INDEX]
    }


def _table_data(
    artifacts: Dict[str, Artifact], artifact_id: str
) -> Tuple[List[str], List[List[Any]]]:
    artifact = artifacts.get(artifact_id)
    result = getattr(artifact, "result", None)
    inline = result.inline if result is not None else None
    if isinstance(inline, dict):
        columns = inline.get("columns")
        rows = inline.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            raw_columns = columns[:MAX_RENDER_TABLE_COLUMNS]
            return [_bounded_cell(item) for item in raw_columns], [
                list(row)[: len(raw_columns)]
                if isinstance(row, (list, tuple))
                else [row.get(str(column)) for column in raw_columns]
                for row in rows[:MAX_RENDER_TABLE_ROWS]
                if isinstance(row, (list, tuple, dict))
            ]
    if isinstance(inline, list) and inline and isinstance(inline[0], dict):
        raw_columns = list(inline[0])[:MAX_RENDER_TABLE_COLUMNS]
        rows = [row for row in inline[:MAX_RENDER_TABLE_ROWS] if isinstance(row, dict)]
        return [_bounded_cell(item) for item in raw_columns], [
            [row.get(column) for column in raw_columns] for row in rows
        ]
    return [], []


def render_report_html(document: ReportDocument) -> str:
    """Render a script-free, resource-bounded standalone HTML preview."""
    artifacts = _artifact_index(document)
    body = _RenderBuffer()
    block_count = 0
    presentation = document.metadata.get("presentation")
    presentation_html = (
        presentation.get("content")
        if isinstance(presentation, dict)
        and presentation.get("format") == "html"
        and isinstance(presentation.get("content"), str)
        else None
    )
    if presentation_html is not None:
        # Keep the original report layout while isolating model-authored HTML.
        # The sandbox omits allow-scripts and the CSP blocks scripts, forms,
        # remote images, and nested frames while allowing common inline charts.
        bounded_presentation = normalize_report_html(
            presentation_html[:MAX_RENDER_PRESENTATION_CHARS]
        )
        body.append(
            '<iframe class="report-presentation" title="Generated report" '
            'sandbox="allow-same-origin" referrerpolicy="no-referrer" '
            'srcdoc="' + html.escape(bounded_presentation, quote=True) + '"></iframe>'
        )
        if len(presentation_html) > MAX_RENDER_PRESENTATION_CHARS:
            body.append(f"<p>{_TRUNCATED}</p>")
    else:
        for section in document.sections[:MAX_RENDER_SECTIONS]:
            if body.exhausted:
                break
            section_body = _RenderBuffer()
            for block in section.blocks:
                if block_count >= MAX_RENDER_BLOCKS or body.exhausted:
                    break
                block_count += 1
                title = html.escape(_bounded_cell(block.title or block.type.title()))
                content = ""
                if isinstance(block, MetricBlock):
                    value = (
                        block.display_value
                        if block.display_value is not None
                        else block.value
                    )
                    content = (
                        f'<div class="metric">{html.escape(_bounded_cell(value))}'
                        f"{html.escape(_bounded_cell(block.unit or ''))}</div>"
                    )
                elif isinstance(block, (InsightBlock, TextBlock)):
                    content = f"<p>{html.escape(_bounded_text(block.content))}</p>"
                elif isinstance(block, TableBlock):
                    columns, rows = _table_data(artifacts, block.data_artifact_id)
                    header = "".join(
                        f"<th>{html.escape(column)}</th>" for column in columns
                    )
                    table_rows = "".join(
                        "<tr>"
                        + "".join(
                            f"<td>{html.escape(_bounded_cell(value))}</td>"
                            for value in row[: len(columns)]
                        )
                        + "</tr>"
                        for row in rows
                    )
                    content = (
                        f"<table><thead><tr>{header}</tr></thead>"
                        f"<tbody>{table_rows}</tbody></table>"
                    )
                elif isinstance(block, ChartBlock):
                    content = (
                        "<p>Chart artifact: <code>"
                        + html.escape(_bounded_cell(block.chart_artifact_id))
                        + "</code></p>"
                    )
                evidence = _evidence_line(block)
                if evidence:
                    content += f'<p class="evidence">{html.escape(evidence)}</p>'
                section_body.append(
                    '<article data-block-id="'
                    + html.escape(block.block_id, quote=True)
                    + f'"><h3>{title}</h3>{content}</article>'
                )
            body.append(
                f"<section><h2>{html.escape(_bounded_cell(section.title))}</h2>"
                f"{section_body.render()}</section>"
            )
    if presentation_html is None and (
        block_count >= MAX_RENDER_BLOCKS
        or len(document.sections) > MAX_RENDER_SECTIONS
        or body.exhausted
    ):
        body.append(f"<p>{_TRUNCATED}</p>")

    css = (
        "body{font:15px system-ui;max-width:1100px;margin:0 auto;padding:32px;"
        "color:#172033}h1{font-size:30px}section{margin:28px 0}"
        ".report-presentation{display:block;width:100%;min-height:900px;"
        "border:0;background:white}"
        "article{border:1px solid #e5e7eb;border-radius:10px;padding:18px;"
        "margin:12px 0}.metric{font-size:28px;font-weight:700}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #d1d5db;"
        "padding:8px;text-align:left}.evidence{color:#64748b;font-size:12px;"
        "white-space:pre-wrap}"
    )
    return """<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="%s">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>%s</style>
</head><body><h1>%s</h1><p>Generated: %s</p>%s</body></html>""" % (
        html.escape(REPORT_PREVIEW_CSP, quote=True),
        css,
        html.escape(_bounded_cell(document.title)),
        html.escape(document.created_at.isoformat()),
        body.render(),
    )


__all__ = [
    "MAX_RENDER_CELL_CHARS",
    "MAX_RENDER_OUTPUT_CHARS",
    "MAX_RENDER_TABLE_COLUMNS",
    "MAX_RENDER_TABLE_ROWS",
    "MAX_RENDER_TEXT_CHARS",
    "REPORT_PREVIEW_CSP",
    "render_report_html",
]
