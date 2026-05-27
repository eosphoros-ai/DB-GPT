#!/usr/bin/env python3
"""Rename ui_<hash> keys to semantic names derived from English labels."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOCALES = WEB / "locales"
PAIR = re.compile(r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'", re.M)
UI_KEY = re.compile(r"^ui_[a-f0-9]{6,}$")


def slugify(en_val: str, existing: set[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", en_val.strip().lower())
    base = base.strip("_")[:48] or "ui_label"
    if base[0].isdigit():
        base = f"n_{base}"
    cand = base
    n = 2
    while cand in existing:
        cand = f"{base}_{n}"
        n += 1
    existing.add(cand)
    return cand


def parse_module(path: Path) -> dict[str, str]:
    return dict(PAIR.findall(path.read_text(encoding="utf-8")))


def replace_key_in_file(path: Path, renames: dict[str, str]) -> int:
    text = path.read_text(encoding="utf-8")
    orig = text
    for old, new in sorted(renames.items(), key=lambda x: -len(x[0])):
        text = text.replace(f"'{old}'", f"'{new}'")
        text = text.replace(f'"{old}"', f'"{new}"')
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return 1
    return 0


def rename_in_locale(path: Path, renames: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in renames.items():
        text = re.sub(
            rf"^(\s+){re.escape(old)}(\s*:)",
            rf"\1{new}\2",
            text,
            count=1,
            flags=re.M,
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    renames: dict[str, str] = {}
    reserved: set[str] = set()
    for mod in ("common", "chat", "flow"):
        reserved.update(parse_module(LOCALES / "en" / f"{mod}.ts"))
    reserved -= {k for k in reserved if UI_KEY.match(k)}
    for mod in ("common", "chat", "flow"):
        en = parse_module(LOCALES / "en" / f"{mod}.ts")
        for key, val in en.items():
            if not UI_KEY.match(key):
                continue
            renames[key] = slugify(val, reserved)
    print(f"renaming {len(renames)} ui_* keys")
    for mod in ("common", "chat", "flow"):
        for lang in ("en", "zh", "ru"):
            rename_in_locale(LOCALES / lang / f"{mod}.ts", renames)
    n = 0
    skip_dirs = {"node_modules", ".next", "old_web", "locales"}
    for path in WEB.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if skip_dirs.intersection(path.parts):
            continue
        n += replace_key_in_file(path, renames)
    print(f"updated {n} source files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
