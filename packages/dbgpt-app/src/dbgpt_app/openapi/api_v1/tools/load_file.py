"""load_file tool — bounded summaries of the turn's files.

Session files are described by ``file_id`` + public metadata + inspection
schema/preview + the per-turn materialized local path, so the model can run
free-form analysis with ``code_interpreter`` without guessing paths. The
path is a temporary copy valid only for the current turn; storage URIs and
hashes never appear. Server paths are masked at the share boundary (see
``scrub_react_history_for_share``).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.agent.resource.tool.base import tool

MAX_LOAD_FILE_FILES = 20
MAX_LOAD_FILE_CHARS = 4000

_TRUNCATION_NOTICE = "\n… [observation truncated — request specific file_ids]"


def _text_chunk(content: str) -> Dict[str, Any]:
    return {"output_type": "text", "content": content}


def _text_response(*contents: str) -> str:
    return json.dumps(
        {"chunks": [_text_chunk(content) for content in contents]},
        ensure_ascii=False,
    )


def _summarize_preview(preview: Any, truncated: bool) -> str:
    """Render a one-line schema/preview summary from the inspection."""
    if not isinstance(preview, dict) or not preview:
        return "preview unavailable"
    rows = preview.get("rows")
    if isinstance(rows, list) and rows:
        header = rows[0]
        if isinstance(header, list):
            columns = ", ".join(str(col) for col in header)
            return f"schema: columns [{columns}]; sample rows: {max(len(rows) - 1, 0)}"
    sheets = preview.get("sheets")
    if isinstance(sheets, list):
        names = ", ".join(
            str(sheet.get("name")) for sheet in sheets if isinstance(sheet, dict)
        )
        return f"schema: sheets [{names}]"
    text = preview.get("text")
    if isinstance(text, str):
        snippet = " ".join(text.split())[:200]
        return f"preview: {snippet}"
    payload = json.dumps(preview, ensure_ascii=False, default=str)
    return f"preview: {payload[:200]}"


def _file_section(
    manifest: Any, inspection: Optional[Dict[str, Any]], path: Optional[str] = None
) -> str:
    status = (
        manifest.status.value
        if hasattr(manifest.status, "value")
        else str(manifest.status)
    )
    lines = [
        f"[{manifest.file_id}] {manifest.name} — {manifest.kind}, "
        f"{manifest.media_type}, {manifest.size} B, {status}"
    ]
    if path:
        lines.append(f"  path: {path} (valid for this turn only)")
    if inspection is not None:
        preview = inspection.get("preview")
        truncated = bool(inspection.get("truncated"))
        flag = "truncated" if truncated else "not truncated"
        lines.append(f"  {_summarize_preview(preview, truncated)}; {flag}")
    return "\n".join(lines)


def _validate_selection(
    file_ids: Any, manifests: List[Any]
) -> Tuple[List[Any], List[str]]:
    """Validate the optional file_ids subset for the turn's files.

    Returns ``(selected_manifests, error_lines)``. Malformed selections are
    reported as deterministic error lines instead of raising.
    """
    if file_ids is None:
        return list(manifests[:MAX_LOAD_FILE_FILES]), []
    if (
        isinstance(file_ids, str)
        or not isinstance(file_ids, (list, tuple))
        or not file_ids
        or any(
            not isinstance(file_id, str) or not file_id.strip() for file_id in file_ids
        )
        or len(file_ids) != len(set(file_ids))
    ):
        return [], ["invalid file_ids: provide a non-empty list of file ids"]
    available = {manifest.file_id: manifest for manifest in manifests}
    selected: List[Any] = []
    missing: List[str] = []
    for file_id in file_ids:
        manifest = available.get(file_id)
        if manifest is None:
            missing.append(file_id)
        else:
            selected.append(manifest)
    errors = [f"files not found: {', '.join(missing)}"] if missing else []
    return selected, errors


def make_load_file(react_state: Dict[str, Any]):
    @tool(
        description=(
            "Inspect files attached to this conversation. Returns public file "
            "metadata, schema/preview summaries and the per-turn materialized "
            "local path, bounded in size. Use the returned path with "
            "code_interpreter for free-form analysis; the path is valid only "
            "for the current turn — call load_file again in a new turn. "
            "Reference files by file_id."
            'Parameters: {"file_ids": "optional subset of file ids"}'
        )
    )
    def load_file(file_ids: Optional[List[str]] = None) -> str:
        """Return bounded info for the selected files."""
        manifests = list(react_state.get("session_files") or [])
        inspections = react_state.get("session_file_inspections") or {}
        paths = react_state.get("session_file_paths") or {}

        # Legacy ``ext_info.file_path`` flow (no session file manifests):
        # report the uploaded file's name and current local path.
        if not manifests:
            legacy_path = react_state.get("file_path")
            if not legacy_path:
                return _text_response("No file uploaded")
            if file_ids is not None:
                return _text_response(
                    "files not found: file_ids require uploaded session files"
                )
            return _text_response(
                f"File uploaded: {Path(str(legacy_path)).name}",
                f"path: {legacy_path}",
                "File provided by user upload",
            )

        selected, errors = _validate_selection(file_ids, manifests)
        if file_ids is not None and not selected and errors:
            return _text_response(*errors)

        header = f"Session files ({len(selected)} selected):"
        body_parts: List[str] = [header]
        used = len(header)
        shown = 0
        hidden = 0
        for manifest in selected:
            if shown >= MAX_LOAD_FILE_FILES:
                hidden += 1
                continue
            section = _file_section(
                manifest,
                inspections.get(manifest.file_id),
                paths.get(manifest.file_id),
            )
            block = f"\n{shown + 1}. {section}"
            if used + len(block) > MAX_LOAD_FILE_CHARS:
                hidden += 1
                continue
            body_parts.append(block)
            used += len(block)
            shown += 1

        notice = ""
        if hidden:
            notice = f"\n… [observation truncated — {hidden} more file(s) not shown]"
        guide = (
            "\nReference files by file_id; use the shown path with "
            "code_interpreter for free-form analysis (this turn only)."
        )
        content = "".join(body_parts) + notice + guide
        if len(content) > MAX_LOAD_FILE_CHARS:
            content = content[:MAX_LOAD_FILE_CHARS] + _TRUNCATION_NOTICE
        chunks: List[Dict[str, Any]] = [_text_chunk(content)]
        chunks.extend(_text_chunk(error) for error in errors)
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return load_file
