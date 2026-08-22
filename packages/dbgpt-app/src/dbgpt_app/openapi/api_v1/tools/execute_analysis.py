"""execute_analysis tool — bounded multi-file table analysis.

File locations reach the generated runner only through the subprocess
environment (``FILE_PATH``/``FILES_JSON``/``ANALYZE_IDS``/``ANALYZE_NAMES``);
the runner source itself is a constant string with no path interpolation,
so hostile display names or paths cannot inject code. Public IDs map to
private local paths only inside the execution process.
"""

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.agent.resource.tool.base import tool

from .code_interpreter import _run_python_file, build_execution_env

# Strict single-component allowlist mirroring the session-file registry's
# ``_sanitize_scope_component`` semantics, so a conversation id can never
# escape the ``PILOT_PATH/tmp`` work-dir root or hit platform edge cases.
_SAFE_CONV_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~=-]*")
_MAX_CONV_ID_BYTES = 128
_WINDOWS_DEVICE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)


def _sanitize_conv_id(value: Any) -> Optional[str]:
    """Return ``value`` only when it is a filesystem-safe path component.

    Mirrors the registry's ``_sanitize_scope_component`` semantics: rejects
    blanks, path separators, NUL bytes, dot-only names, overlong values and
    reserved Windows device names. ``None`` means "not usable, fail closed".
    """
    if not isinstance(value, str) or not value.strip():
        return None
    if (
        "\x00" in value
        or "/" in value
        or "\\" in value
        or (os.sep and os.sep in value)
        or (os.altsep and os.altsep in value)
    ):
        return None
    if value in (".", "..") or not _SAFE_CONV_ID_RE.fullmatch(value):
        return None
    if len(value.encode("utf-8")) > _MAX_CONV_ID_BYTES:
        return None
    stem = value.split(".", 1)[0].upper()
    if stem in _WINDOWS_DEVICE_NAMES:
        return None
    return value


# The runner is intentionally constant: every variable value (paths, file
# ids, display names) is read from ``os.environ`` inside the child process.
_ANALYSIS_RUNNER = """
import json
import os

import pandas as pd


def _read_frame(path):
    lower = path.lower()
    if lower.endswith((".xls", ".xlsx")):
        return pd.read_excel(path)
    if lower.endswith(".tsv"):
        return pd.read_csv(path, sep="\\t")
    return pd.read_csv(path)


def _summarize(path):
    df = _read_frame(path)
    return {
        "shape": list(df.shape),
        "columns": [str(column) for column in df.columns],
        "dtypes": {
            str(column): str(dtype) for column, dtype in df.dtypes.items()
        },
        "head": df.head(5).to_dict(orient="records"),
    }


def main():
    mapping = {}
    files_json = os.environ.get("FILES_JSON")
    if files_json:
        with open(files_json, "r", encoding="utf-8") as handle:
            mapping = json.load(handle)
    primary = os.environ.get("FILE_PATH")
    names = json.loads(os.environ.get("ANALYZE_NAMES") or "{}")
    analyze_ids = json.loads(os.environ.get("ANALYZE_IDS") or "[]")
    if not mapping and primary:
        mapping = {"file": primary}
    if not analyze_ids:
        analyze_ids = list(mapping.keys())
    results = []
    for file_id in analyze_ids:
        path = mapping.get(file_id)
        name = names.get(file_id) or (os.path.basename(path) if path else file_id)
        if not path:
            results.append(
                {"file_id": file_id, "name": name, "error": "file not found"}
            )
            continue
        try:
            summary = _summarize(path)
        except Exception as exc:  # noqa: BLE001
            message = str(exc).replace(path, "<file>")
            results.append(
                {
                    "file_id": file_id,
                    "name": name,
                    "error": f"{type(exc).__name__}: {message}",
                }
            )
            continue
        summary["file_id"] = file_id
        summary["name"] = name
        results.append(summary)
    print(json.dumps({"files": results}, ensure_ascii=False, default=str))


main()
"""


def _text_chunk(content: str) -> Dict[str, Any]:
    return {"output_type": "text", "content": content}


def _table_chunk(columns: List[Any], rows: List[Any]) -> Dict[str, Any]:
    return {
        "output_type": "table",
        "content": {
            "columns": [
                {"title": col, "dataIndex": col, "key": col} for col in columns
            ],
            "rows": rows,
        },
    }


def _chart_chunk(
    dtypes: Dict[str, str], head_rows: List[Any]
) -> Optional[Dict[str, Any]]:
    numeric_columns = [
        col
        for col, dtype in (dtypes or {}).items()
        if "int" in dtype or "float" in dtype
    ]
    if not numeric_columns or not isinstance(head_rows, list):
        return None
    series_col = numeric_columns[0]
    data = [
        {"x": idx + 1, "y": row.get(series_col)}
        for idx, row in enumerate(head_rows)
        if isinstance(row, dict) and row.get(series_col) is not None
    ]
    if not data:
        return None
    return {
        "output_type": "chart",
        "content": {"data": data, "xField": "x", "yField": "y"},
    }


def _scrub(text: str, secrets: List[str]) -> str:
    """Remove internal paths from any user-visible text."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<file>")
    return text


def _validate_selection(
    file_ids: Any, manifests: List[Any]
) -> Tuple[List[Any], List[str]]:
    """Validate the optional subset against the turn's session files."""
    if file_ids is None:
        return list(manifests), []
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


async def _run_analysis(
    *,
    react_state: Dict[str, Any],
    analyze_ids: List[str],
    analyze_names: Dict[str, str],
    files_json_path: Optional[str],
) -> Tuple[List[Dict[str, Any]], str]:
    """Execute the safe analysis runner and parse its JSON output.

    Returns ``(file_results, failure_message)`` where ``failure_message``
    is empty on success.
    """
    from dbgpt.configs.model_config import PILOT_PATH

    cid = _sanitize_conv_id(react_state.get("conv_id") or "default")
    if cid is None:
        # Fail closed before any filesystem write so a hostile id can never
        # place the runner script outside ``PILOT_PATH/tmp``.
        return [], "Analysis failed: invalid conversation id"
    work_dir = os.path.join(PILOT_PATH, "tmp", cid)
    os.makedirs(work_dir, exist_ok=True)
    script_path = os.path.join(work_dir, f"_analysis_{uuid.uuid4().hex}.py")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(_ANALYSIS_RUNNER)

    # Scrub every internal path (and its resolved equivalent) that a
    # runner-level traceback could leak, including the script path and work
    # dir — the work dir embeds the conversation id. Longer paths must come
    # before their parents so prefix replacement cannot leave a stub.
    secrets = [
        script_path,
        os.path.realpath(script_path),
        work_dir,
        os.path.realpath(work_dir),
        files_json_path or "",
        react_state.get("file_path") or "",
    ]
    if files_json_path:
        try:
            mapping = json.loads(Path(files_json_path).read_text(encoding="utf-8"))
            secrets.extend(str(value) for value in mapping.values())
        except Exception:
            pass
    try:
        returncode, stdout, stderr = await _run_python_file(
            script_path,
            cwd=work_dir,
            env=build_execution_env(
                work_dir=work_dir,
                file_path=react_state.get("file_path"),
                files_json_path=files_json_path,
                extra={
                    "ANALYZE_IDS": json.dumps(analyze_ids, ensure_ascii=False),
                    "ANALYZE_NAMES": json.dumps(analyze_names, ensure_ascii=False),
                },
            ),
            timeout=60,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    if returncode is None:
        return [], "Analysis failed: execution timed out"
    output_text = stdout.decode("utf-8", errors="replace").strip()
    if returncode != 0:
        # Scrub before truncating: slicing first could cut a secret mid-way
        # and leave a partial path behind that no longer matches.
        error_text = _scrub(stderr.decode("utf-8", errors="replace").strip(), secrets)
        return [], f"Analysis failed: {error_text[:500]}"
    try:
        payload = json.loads(output_text.splitlines()[-1])
        files = payload.get("files")
        if isinstance(files, list):
            # Defense in depth: even if the runner leaks a path inside an
            # error message, the tool output is scrubbed before surfacing.
            for entry in files:
                if isinstance(entry, dict) and isinstance(entry.get("error"), str):
                    entry["error"] = _scrub(entry["error"], secrets)
            return files, ""
    except Exception:
        pass
    return [], f"Analysis failed: {_scrub(output_text, secrets)[:500]}"


def _is_excel_skill(meta: Any) -> bool:
    name = (meta.name or "").lower()
    desc = (meta.description or "").lower()
    tags = [str(tag).lower() for tag in (meta.tags or [])]
    return any(
        token in name or token in desc or token in tags
        for token in ["excel", "xlsx", "xls", "spreadsheet"]
    )


def _file_summary_chunk(entry: Dict[str, Any], *, include_name: bool) -> Dict[str, Any]:
    summary = {
        "shape": entry.get("shape"),
        "columns": entry.get("columns"),
        "dtypes": entry.get("dtypes"),
        "head": entry.get("head"),
    }
    if include_name:
        summary = {
            "file_id": entry.get("file_id"),
            "name": entry.get("name"),
            **summary,
        }
    return {"output_type": "json", "content": summary}


def make_execute_analysis(react_state: Dict[str, Any]):
    @tool(
        description=(
            "Execute quick analysis on the uploaded Excel/CSV file(s). "
            'Parameters: {"file_ids": "optional subset of file ids; '
            'defaults to all files selected for this turn"}'
        )
    )
    async def execute_analysis(file_ids: Optional[List[str]] = None) -> str:
        """Analyze the selected files; partial failures stay visible."""
        manifests = list(react_state.get("session_files") or [])

        # ── Session-file (multi-file) flow ──────────────────────────────
        if manifests:
            selected, errors = _validate_selection(file_ids, manifests)
            if file_ids is not None and not selected:
                chunks = [_text_chunk(error) for error in errors]
                chunks.append(_text_chunk("No analyzable files."))
                return json.dumps({"chunks": chunks}, ensure_ascii=False)
            analyze_ids = [manifest.file_id for manifest in selected]
            analyze_names = {manifest.file_id: manifest.name for manifest in selected}
            files, failure = await _run_analysis(
                react_state=react_state,
                analyze_ids=analyze_ids,
                analyze_names=analyze_names,
                files_json_path=react_state.get("files_json_path"),
            )
            chunks: List[Dict[str, Any]] = [
                {"output_type": "code", "content": _ANALYSIS_RUNNER.strip()}
            ]
            if failure:
                chunks.append(_text_chunk(failure))
                return json.dumps({"chunks": chunks}, ensure_ascii=False)
            ok_entries = [entry for entry in files if not entry.get("error")]
            failed_entries = [entry for entry in files if entry.get("error")]
            first_ok = True
            for entry in files:
                if entry.get("error"):
                    continue
                chunks.append(_file_summary_chunk(entry, include_name=True))
                if first_ok:
                    columns = entry.get("columns") or []
                    head_rows = entry.get("head") or []
                    chunks.append(_table_chunk(columns, head_rows))
                    chart = _chart_chunk(entry.get("dtypes") or {}, head_rows)
                    if chart:
                        chunks.append(chart)
                    first_ok = False
            for entry in failed_entries:
                chunks.append(
                    _text_chunk(
                        f"File {entry.get('name')} analysis failed: "
                        f"{entry.get('error')}"
                    )
                )
            chunks.extend(_text_chunk(error) for error in errors)
            if not ok_entries:
                chunks.append(_text_chunk("No analyzable files."))
            return json.dumps({"chunks": chunks}, ensure_ascii=False)

        # ── Legacy single-file flow ─────────────────────────────────────
        matched = react_state.get("matched")
        if not react_state.get("file_path"):
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file to analyze"}]},
                ensure_ascii=False,
            )
        if matched and not _is_excel_skill(matched.metadata):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Selected skill is not for Excel analysis",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        legacy_path = str(react_state["file_path"])
        files, failure = await _run_analysis(
            react_state=react_state,
            analyze_ids=["file"],
            analyze_names={"file": Path(legacy_path).name},
            files_json_path=None,
        )
        chunks = [{"output_type": "code", "content": _ANALYSIS_RUNNER.strip()}]
        if failure:
            chunks.append(_text_chunk(failure))
            return json.dumps({"chunks": chunks}, ensure_ascii=False)
        ok_entries = [entry for entry in files if not entry.get("error")]
        failed_entries = [entry for entry in files if entry.get("error")]
        for entry in ok_entries[:1]:
            chunks.append(_file_summary_chunk(entry, include_name=False))
            columns = entry.get("columns") or []
            head_rows = entry.get("head") or []
            chunks.append(_table_chunk(columns, head_rows))
            chart = _chart_chunk(entry.get("dtypes") or {}, head_rows)
            if chart:
                chunks.append(chart)
        for entry in failed_entries:
            chunks.append(
                _text_chunk(
                    f"File {entry.get('name')} analysis failed: {entry.get('error')}"
                )
            )
        if not ok_entries:
            chunks.append(_text_chunk("No analyzable files."))
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return execute_analysis
