#!/usr/bin/env python3
"""One-shot fix for agentic_data_api.py copied to /tmp/agentic_data_api.py on deploy host."""
from __future__ import annotations

import re
from pathlib import Path

p = Path("/tmp/agentic_data_api.py")
text = p.read_text(encoding="utf-8")

# Remove broken inline comments that swallowed commas
text = re.sub(
    r'("Мысль / действие / результат")\s*#\s*DBGPT_RU_AGENT_UI\s*,?',
    r"\1,",
    text,
)
text = re.sub(
    r'("Думаю"),\s*#\s*DBGPT_RU_AGENT_UI',
    r'"Думаю",',
    text,
)
text = text.replace(",,", ",")

# Fix broken html block if present
text = re.sub(
    r'"content": \(\s*'
    r'f"Файл не найден: \{file_path\}\. "\s*'
    r"['\"].*?"
    r"Не используйте file_path\.\s*"
    r"\)\s*#?\s*DBGPT_RU_AGENT_UI,?",
    (
        '"content": (\n'
        '                                        f"Файл не найден: {file_path}. "\n'
        '                                        "Передайте готовый HTML в параметре html, например: "\n'
        '                                        \'{"html": "<!DOCTYPE html>...", "title": "Отчёт"}. "\n'
        '                                        "Не используйте file_path."\n'
        "                                    )"
    ),
    text,
    count=1,
    flags=re.DOTALL,
)

p.write_text(text, encoding="utf-8")
compile(text, str(p), "exec")
print("fix_agentic_on_host: OK")
