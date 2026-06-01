#!/usr/bin/env python3
"""Добавить default БД fmcg вне блока ext_info (исправление v1 патча)."""
from pathlib import Path

MARKER = "# DBGPT_DB_DEFAULT_OUTER"
TARGET = Path(
    "/app/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py"
)

def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("fix_db_default_outer: уже есть")
        return

    old_inner = (
        "        database_name = dialogue.ext_info.get(\"database_name\")\n"
        "        if not database_name:\n"
        "            database_name = os.environ.get(\"DBGPT_DEFAULT_DATABASE\", \"fmcg\")"
        "  # DBGPT_RU_PATCH_APPLIED"
    )
    if old_inner in text:
        text = text.replace(
            old_inner,
            '        database_name = dialogue.ext_info.get("database_name")',
            1,
        )

    anchor = "\n    def infer_phase(action: str) -> str:"
    insert = (
        f"\n    if not database_name:\n"
        f'        database_name = os.environ.get("DBGPT_DEFAULT_DATABASE", "fmcg")'
        f"  {MARKER}\n"
    )
    if anchor not in text:
        raise SystemExit("anchor not found")
    text = text.replace(anchor, insert + anchor, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("fix_db_default_outer: OK")

if __name__ == "__main__":
    main()
