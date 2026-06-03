#!/usr/bin/env python3
"""Replace hardcoded Chinese agent UI strings in installed agentic_data_api.py."""
from __future__ import annotations

import os
from pathlib import Path

API_PATH = Path(
    "/app/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py"
)


def main() -> None:
    lang = (os.getenv("DBGPT_LANG") or os.getenv("LANGUAGE") or "ru").lower()
    if not lang.startswith("ru"):
        print("patch_agentic_ru_strings: skip (lang is not ru)")
        return

    path = API_PATH
    try:
        import dbgpt_app.openapi.api_v1.agentic_data_api as mod  # noqa: F401

        path = Path(mod.__file__)
    except SyntaxError:
        from repair_agentic_api_syntax import main as repair

        repair()
    except ImportError as e:
        print(f"patch_agentic_ru_strings: import failed: {e}")
        return

    text = path.read_text(encoding="utf-8")
    if "思考中" not in text and "Думаю" in text:
        print("patch_agentic_ru_strings: thinking strings already ru")
    else:
        replacements = [
            ('"思考中",', '"Думаю",'),
            ('"Thought/Action/Observation",', '"Мысль / действие / результат",'),
            ('"Thought/Action/Observation"', '"Мысль / действие / результат"'),
        ]
        for old, new in replacements:
            if old in text:
                text = text.replace(old, new)
                print(f"patch_agentic_ru_strings: replaced {old!r}")

    old_block = '''                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": f"File not found: {file_path}",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )'''
    new_block = '''                    msg = (
                        f"Файл не найден: {file_path}. "
                        "Передайте готовый HTML в параметре html, например: "
                        '{"html": "<!DOCTYPE html>...", "title": "Отчёт"}. '
                        "Не используйте file_path."
                    )
                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": msg,
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )'''
    if old_block in text:
        text = text.replace(old_block, new_block, 1)
        print("patch_agentic_ru_strings: patched html file_path error msg")

    path.write_text(text, encoding="utf-8")
    from repair_agentic_api_syntax import main as repair

    repair()
    print(f"patch_agentic_ru_strings: OK {path}")


if __name__ == "__main__":
    main()
