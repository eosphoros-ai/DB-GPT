"""Skill entry point for deterministic, page-backed annual-report extraction."""

import json
import sys
from pathlib import Path

from financial_document import extract_document


def extract_financials(file_path):
    """Extract annual-report facts or return a JSON-serializable error."""
    try:
        return extract_document(Path(file_path))
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
