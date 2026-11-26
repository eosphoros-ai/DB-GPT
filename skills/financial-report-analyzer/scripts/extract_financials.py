"""Skill entry point for deterministic, page-backed annual-report extraction."""

import importlib.util
import json
import sys
from pathlib import Path


def _load_sibling(name):
    """Support both CLI execution and importlib-based skill callers."""
    scripts = Path(__file__).resolve().parent
    path = str(scripts)
    if path not in sys.path:
        sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location(name, scripts / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_text = _load_sibling("financial_text")
_column_date = _text._column_date
_column_periods = _text._column_periods
_opening_restatement = _text._opening_restatement
_select_balance_sheet_candidate = _text._select_balance_sheet_candidate


def extract_financials(file_path):
    """Extract annual-report facts or return a JSON-serializable error."""
    try:
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            return _text.extract_text_report(path)
        from financial_document import extract_document

        return extract_document(path)
    except Exception as exc:
        # This is the tool boundary: damaged/encrypted PDFs must return JSON too.
        # stderr may also be captured by a tool runner; keep paths out of both streams.
        print(f"PDF extraction failed ({type(exc).__name__})", file=sys.stderr)
        return {
            "error": True,
            "code": "PDF_EXTRACTION_FAILED",
            "errorType": type(exc).__name__,
            "message": "PDF extraction failed; the file may be unavailable, damaged, "
            "encrypted, or not a text-based annual report.",
        }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        parsed = json.loads(arg)
        file_path = parsed.get("file_path", "") if isinstance(parsed, dict) else parsed
    except json.JSONDecodeError:
        file_path = arg
    result = (
        extract_financials(file_path)
        if isinstance(file_path, str) and file_path
        else {"error": True, "message": "Missing required parameter: file_path"}
    )
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1 if result.get("error") else 0)
