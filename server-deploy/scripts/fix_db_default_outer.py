#!/usr/bin/env python3
"""Default DB from DBGPT_DEFAULT_DATABASE when UI does not pass database_name (ops, not i18n fork)."""
from __future__ import annotations

import os
from pathlib import Path

MARKER = "# DBGPT_DB_DEFAULT_OUTER"
TARGET = Path(
    "/app/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py"
)

INSERT = f"""
    if not database_name:
        database_name = os.environ.get("DBGPT_DEFAULT_DATABASE", "fmcg")  {MARKER}
"""

ANCHOR = '        database_name = dialogue.ext_info.get("database_name")'


def main() -> None:
    path = TARGET
    if not path.is_file():
        print(f"fix_db_default_outer: missing {path}")
        return
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print("fix_db_default_outer: already applied")
        return
    if ANCHOR not in text:
        print("fix_db_default_outer: anchor not found")
        return
    text = text.replace(ANCHOR, ANCHOR + INSERT, 1)
    path.write_text(text, encoding="utf-8")
    print("fix_db_default_outer: OK")


if __name__ == "__main__":
    main()
