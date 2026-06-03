#!/usr/bin/env python3
"""Set ru locale values from deploy en_to_ru when ru still equals en."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "web" / "locales"
DEPLOY_EN = Path(r"z:\Projects\DBTGPT\deploy\locales\translations\en_to_ru.json")
DEPLOY_ZH = Path(r"z:\Projects\DBTGPT\deploy\locales\replacements\all_zh_ru.json")
PAIR = re.compile(r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'", re.M)

# Keep English for identifiers / acronyms / very short tokens
KEEP_EN_VALUES = {
    "PDF",
    "JSON",
    "URL",
    "topk",
    "recall_score",
    "recall_type",
    "chunk_size",
    "chunk_overlap",
    "retrieve_mode",
    "model",
    "Embedding",
    "Chunks",
    "Content",
    "Meta Data",
    "Vector",
    "Chat",
    "Type",
    "Name",
    "Status",
    "Process",
    "Automatic",
    "Sync",
    "Back",
    "Finish",
    "Next",
    "Submit",
    "Delete",
    "Operation",
    "Details",
    "Result",
    "Description",
    "Storage",
    "Domain",
    "Text",
    "Document",
    "Yes",
    "No",
    "Import",
    "Export",
    "value",
    "title",
}


def parse_ts(path: Path) -> dict[str, str]:
    return dict(PAIR.findall(path.read_text(encoding="utf-8")))


def write_ts_values(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, val in updates.items():
        esc = val.replace("\\", "\\\\").replace("'", "\\'")
        text, n = re.subn(
            rf"^(\s+{re.escape(key)}\s*:\s*)'(?:\\'|[^'])*'",
            rf"\1'{esc}'",
            text,
            count=1,
            flags=re.M,
        )
        if not n:
            print(f"warn: missing key {key} in {path.name}")
    path.write_text(text, encoding="utf-8")


CJK = re.compile(r"[\u4e00-\u9fff]")


def main() -> int:
    if not DEPLOY_EN.is_file():
        print(f"missing {DEPLOY_EN}", file=sys.stderr)
        return 1
    en_to_ru: dict[str, str] = json.loads(DEPLOY_EN.read_text(encoding="utf-8"))
    zh_ru: dict[str, str] = (
        json.loads(DEPLOY_ZH.read_text(encoding="utf-8")) if DEPLOY_ZH.is_file() else {}
    )
    total = 0
    for mod in ("common", "chat", "flow"):
        en = parse_ts(LOCALES / "en" / f"{mod}.ts")
        zh_path = LOCALES / "zh" / f"{mod}.ts"
        zh = parse_ts(zh_path) if zh_path.is_file() else {}
        ru_path = LOCALES / "ru" / f"{mod}.ts"
        ru = parse_ts(ru_path)
        updates: dict[str, str] = {}
        for key, ru_v in ru.items():
            if key not in en:
                continue
            en_v = en[key]
            if ru_v != en_v:
                continue
            if en_v in KEEP_EN_VALUES or len(en_v) <= 3:
                continue
            new: str | None = None
            if en_v in en_to_ru:
                new = en_to_ru[en_v]
            elif en_v.lower() in en_to_ru:
                new = en_to_ru[en_v.lower()]
            elif key in zh:
                zh_v = zh[key]
                if zh_v in zh_ru:
                    cand = zh_ru[zh_v]
                    if not CJK.search(cand):
                        new = cand
            if new and new != ru_v:
                updates[key] = new
        if updates:
            write_ts_values(ru_path, updates)
            total += len(updates)
            print(f"{mod}: filled {len(updates)}")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
