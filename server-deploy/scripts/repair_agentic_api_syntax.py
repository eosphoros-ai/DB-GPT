#!/usr/bin/env python3
"""Fix commas broken by patch_agentic_ru_strings (# comment swallowed trailing commas)."""
from __future__ import annotations

import re
from pathlib import Path

API_PATH = Path(
    "/app/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py"
)


def main() -> None:
    path = API_PATH
    if not path.is_file():
        print(f"repair: missing {path}")
        return

    text = path.read_text(encoding="utf-8")
    changed = False

    # Comma after value must not be placed only in a trailing comment.
    text2, n = re.subn(
        r'("Мысль / действие / результат")\s*#\s*DBGPT_RU_AGENT_UI\s*,',
        r"\1,",
        text,
    )
    if n:
        text = text2
        changed = True
        print(f"repair: restored {n} comma(s) after react detail string")

    text2, n = re.subn(
        r'("Думаю"),\s*#\s*DBGPT_RU_AGENT_UI\n(\s+)("Мысль / действие / результат")(\s*#\s*DBGPT_RU_AGENT_UI,?)?',
        r'\1,\n\2\3,',
        text,
    )
    if n:
        text = text2
        changed = True
        print("repair: fixed build_step argument commas")

    fixed_msg = (
        '"content": (\n'
        '                                        f"Файл не найден: {file_path}. "\n'
        '                                        "Передайте готовый HTML в параметре html, например: "\n'
        '                                        \'{"html": "<!DOCTYPE html>...", "title": "Отчёт"}. "\n'
        '                                        "Не используйте file_path."\n'
        "                                    )"
    )
    if "Передайте HTML в параметре html: \"" in text:
        text, n = re.subn(
            r'"content": \(\s*'
            r'f"Файл не найден: \{file_path\}\. "\s*'
            r"['\"].*?"
            r"Не используйте file_path\.\s*"
            r"\)\s*#?\s*DBGPT_RU_AGENT_UI,?",
            fixed_msg,
            text,
            count=1,
            flags=re.DOTALL,
        )
        if n:
            changed = True
            print("repair: fixed html_interpreter message block")

    if changed:
        path.write_text(text, encoding="utf-8")
        print(f"repair: wrote {path}")
    else:
        print("repair: nothing to fix")


if __name__ == "__main__":
    main()
