#!/usr/bin/env python3
"""Set English locale values for phase2 keys (replace mistaken Chinese in en/*.ts)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "web" / "locales"
DEPLOY = ROOT.parent.parent / "DBTGPT" / "deploy" / "locales"
CJK = re.compile(r"[\u4e00-\u9fff]")
PAIR = re.compile(
    r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'",
    re.M,
)


def load_json(path: Path) -> dict[str, str]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    zh_ru = load_json(DEPLOY / "replacements" / "all_zh_ru.json")
    en_to_ru = load_json(DEPLOY / "translations" / "en_to_ru.json")
    ru_to_en = {v: k for k, v in en_to_ru.items() if v}

    fixed = 0
    for mod in ("common", "chat", "flow"):
        en_path = LOCALES / "en" / f"{mod}.ts"
        ru_path = LOCALES / "ru" / f"{mod}.ts"
        zh_path = LOCALES / "zh" / f"{mod}.ts"
        en = dict(PAIR.findall(en_path.read_text(encoding="utf-8")))
        ru = dict(PAIR.findall(ru_path.read_text(encoding="utf-8")))
        zh = dict(PAIR.findall(zh_path.read_text(encoding="utf-8")))
        updates: dict[str, str] = {}
        for key, en_val in en.items():
            if not CJK.search(en_val):
                continue
            zh_val = zh.get(key, en_val)
            ru_val = ru.get(key, "")
            new_en = None
            if ru_val in ru_to_en:
                new_en = ru_to_en[ru_val]
            elif zh_val in zh_ru and zh_ru[zh_val] in ru_to_en:
                new_en = ru_to_en[zh_ru[zh_val]]
            if new_en and not CJK.search(new_en):
                updates[key] = new_en
        if not updates:
            continue
        text = en_path.read_text(encoding="utf-8")
        for key, val in updates.items():
            esc = val.replace("\\", "\\\\").replace("'", "\\'")
            text, n = re.subn(
                rf"^(\s+{re.escape(key)}\s*:\s*)'(?:\\'|[^'])*'",
                rf"\1'{esc}'",
                text,
                count=1,
                flags=re.M,
            )
            if n:
                fixed += 1
        en_path.write_text(text, encoding="utf-8")
        print(f"{mod}: fixed {len(updates)} en strings")
    print(f"total en key fixes: {fixed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
