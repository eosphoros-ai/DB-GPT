"""Render saved snapshots with a prebuilt offline React runtime."""

import json
import os
from pathlib import Path

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .workflow import public_snapshot

DATA_MARKER = "<!--FINANCIAL_REPORT_JSON-->"


def render_export(report, kind, runtime=None):
    payload = json.dumps(
        public_snapshot(report), ensure_ascii=False, allow_nan=False, indent=2
    )
    if kind == "json":
        return payload
    if runtime is None:
        from dbgpt.configs.model_config import SKILLS_DIR

        runtime = os.getenv("DBGPT_FINANCIAL_EXPORT_RUNTIME") or (
            Path(SKILLS_DIR).parent / ".work/financial-analysis/export-runtime.html"
        )
    path = Path(runtime)
    if not path.is_file():
        raise SessionFileApiError(
            503,
            "EXPORT_RUNTIME_MISSING",
            "HTML 导出组件尚未构建，请先生成离线导出组件。",
        )
    shell = path.read_text(encoding="utf-8")
    if shell.count(DATA_MARKER) != 1:
        raise SessionFileApiError(
            503, "EXPORT_RUNTIME_INVALID", "HTML 导出组件无效，请重新构建。"
        )
    # JSON is data in an inert script node. Escape markup delimiters so user/model
    # text cannot close that node and become active HTML or JavaScript.
    safe_json = (
        payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )
    return shell.replace(DATA_MARKER, safe_json)
